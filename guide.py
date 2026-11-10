"""The agents: a Lead that plans, Researchers that search wings of the museum in parallel, and a
Writer that turns the evidence into a cited tour or answer.

Lead (Guide)      reads the request, asks when it is vague, identifies objects from labels, answers
                  counting questions with SQL, and for tours sends Researchers out in parallel.
Researcher 1..n   each searches one slice of the museum (a department, theme or period) in a fresh
                  context and returns candidate objects with the evidence for each.
Writer            writes the tour or answer from the evidence it is given, and nothing else.
plan_route        is code, not a model: it orders stops by walking distance.
"""

import asyncio
import json
import os

import httpx
from agents import Agent, ModelSettings, RunContextWrapper, RunHooks, Runner, function_tool, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel

import met_tools
import route
import wikipedia

set_tracing_disabled(True)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LEAD_MODEL = LitellmModel(model=os.environ.get("LEAD_MODEL", "vertex_ai/gemini-3.5-flash"), api_key="unused")
RESEARCH_MODEL = LitellmModel(model=os.environ.get("RESEARCH_MODEL", "vertex_ai/gemini-3.5-flash-lite"), api_key="unused")
WRITER_MODEL = LitellmModel(model=os.environ.get("WRITER_MODEL", "vertex_ai/gemini-3.5-flash"), api_key="unused")
_extra = {"vertex_location": "global", "timeout": 90, "num_retries": 2}
if PROJECT:
    _extra["vertex_project"] = PROJECT
SETTINGS = ModelSettings(extra_args=_extra)

MAX_RESEARCHERS = 5
LEAD_MAX_TURNS = 16
RESEARCHER_MAX_TURNS = 8
MET_API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"


# --- Run state: the tool-call log every agent writes to, returned by /chat ---


class Run:
    def __init__(self):
        self.tool_calls: list[dict] = []
        self.researchers = 0


class LogHooks(RunHooks):
    """Record every tool call, by any agent, as {agent, name, args, result} for /chat's tool_calls."""

    async def on_tool_end(self, context, agent, tool, result) -> None:
        try:
            args = json.loads(getattr(context, "tool_arguments", "") or "{}")
        except json.JSONDecodeError:
            args = {"raw": getattr(context, "tool_arguments", "")}
        text = result if isinstance(result, str) else json.dumps(result, default=str)
        context.context.tool_calls.append(
            {"agent": agent.name, "name": tool.name, "args": args, "result": text[:4000]})


HOOKS = LogHooks()


def _dump(x) -> str:
    return json.dumps(x, default=str, ensure_ascii=False)


# --- Tools over the snapshot ---


@function_tool
def find_by_accession(accession: str, title_hint: str = "", artist_hint: str = "") -> str:
    """Identify an object from the accession number on its wall label (e.g. '29.100.5').
    Pass the title and artist printed on the label as hints whenever you have them: a misread
    number can match a different real object, and the hints catch that.

    Args:
        accession: The accession number as read from the label.
        title_hint: The title on the label, if visible.
        artist_hint: The artist or culture on the label, if visible.
    """
    return _dump(met_tools.find_by_accession(accession, title_hint, artist_hint))


@function_tool
def find_by_title(title: str, artist: str = "") -> str:
    """Find on-view objects by title (and artist), when the label has no readable number.

    Args:
        title: The title on the label.
        artist: The artist or culture on the label, if any.
    """
    return _dump(met_tools.find_by_title(title, artist))


@function_tool
def get_object(object_id: int) -> str:
    """Everything the snapshot knows about one object: maker, date, medium, gallery, tags, credit
    line, image, and the titles of its Wikipedia articles (object_wikipedia, artist_wikipedia) if any.

    Args:
        object_id: The Met object ID.
    """
    return _dump(met_tools.get_object(object_id))


@function_tool
def search_objects(keywords: str = "", department: str = "", gallery: str = "", culture: str = "", artist: str = "",
                   begin_year: int | None = None, end_year: int | None = None, highlights_only: bool = False,
                   limit: int = 20) -> str:
    """Search objects on view now. Every keyword must match (title, artist, culture, medium, tags,
    department...), so use one to three specific words and try synonyms in separate calls.

    Args:
        keywords: e.g. 'cat', 'horse armor', 'mirror'.
        department: e.g. 'Asian Art', 'Egyptian Art', 'European Paintings', 'Arms and Armor'.
        gallery: an exact gallery number, e.g. '822'.
        culture: e.g. 'Japan', 'Roman', 'Aztec'.
        artist: part of the artist's name.
        begin_year: only objects made in or after this year (negative = BCE).
        end_year: only objects made in or before this year.
        highlights_only: only the Met's designated highlights.
        limit: at most this many results (max 40).
    """
    return _dump(met_tools.search_objects(keywords, department, gallery, culture, artist, begin_year, end_year,
                                          highlights_only, limit=min(limit, 40)))


@function_tool
def gallery_summary(gallery: str) -> str:
    """What one gallery holds: how many objects, which departments and cultures, and its highlights.

    Args:
        gallery: The gallery number, e.g. '131'.
    """
    return _dump(met_tools.gallery_summary(gallery))


@function_tool
def run_sql(sql: str) -> str:
    """Run one read-only SELECT over the on-view snapshot, for counting, comparing and ranking.
    The table's columns are listed below.

    Args:
        sql: A single SELECT statement.
    """
    return _dump(met_tools.run_sql(sql))


run_sql.description = run_sql.description + "\n" + met_tools.SCHEMA


@function_tool
def snapshot_info() -> str:
    """When the data snapshot was built, and how many objects are on view in it."""
    return _dump(met_tools.snapshot_info())


@function_tool
def get_wikipedia(title: str) -> str:
    """Read an English Wikipedia article by exact title. Use only titles from get_object's
    object_wikipedia or artist_wikipedia fields, so the article is about the right object or artist.

    Args:
        title: The article title, e.g. 'Wheat Field with Cypresses'.
    """
    return _dump(wikipedia.fetch(title))


@function_tool
async def plan_route(object_ids: list[int], start_gallery: str = "", minutes_per_stop: float = 6,
                     budget_minutes: float | None = None) -> str:
    """Order tour stops into a walk through the building and estimate the time. Also checks each
    object against the Met's live API, and drops any that are no longer on view.

    Args:
        object_ids: The stops, in any order (8 to 12 is a good tour).
        start_gallery: Where the visitor is now (a gallery number); empty means the main entrance.
        minutes_per_stop: Time to spend at each object.
        budget_minutes: The visitor's total time, if they gave one.
    """
    stops, missing = [], []
    for oid in dict.fromkeys(object_ids):
        o = met_tools.get_object(oid)
        if "error" in o:
            missing.append(oid)
        else:
            stops.append({"object_id": oid, "title": o["title"], "artist": o["artist"], "gallery": o["gallery"],
                          "image_small_url": o.get("image_small_url"), "met_url": o["met_url"]})
    live = await _verify_live([s["object_id"] for s in stops])
    moved = []
    for s in stops:
        v = live.get(s["object_id"])
        if v is None:
            s["live_check"] = "unavailable"
        elif not v["gallery"]:
            s["live_check"] = "not_on_view"
            moved.append(s)
        else:
            s["live_check"] = "on_view"
            if v["gallery"] != s["gallery"]:
                s["gallery"], s["moved_from"] = v["gallery"], s["gallery"]
            if v.get("image_small_url") and not s.get("image_small_url"):
                s["image_small_url"] = v["image_small_url"]
    keep = [s for s in stops if s not in moved]
    result = route.plan(keep, start_gallery, minutes_per_stop, budget_minutes)
    if moved:
        result["notes"].append("Removed (the Met's live data says no longer on view): "
                               + "; ".join(f"{s['title']} ({s['object_id']})" for s in moved))
    if missing:
        result["notes"].append(f"Not in the on-view snapshot, so left out: {missing}")
    if any(s.get("live_check") == "unavailable" for s in keep):
        result["notes"].append("The Met's live API did not answer for some stops; their galleries come from the snapshot.")
    return _dump(result)


async def _verify_live(ids: list[int]) -> dict[int, dict | None]:
    """Ask the Met API whether each object is still on view, a few at a time, failing soft."""
    out: dict[int, dict | None] = {}
    sem = asyncio.Semaphore(4)
    headers = {"User-Agent": "met-guide/0.1 (student course project; educational, non-commercial)"}
    async with httpx.AsyncClient(headers=headers, timeout=6) as client:
        async def one(oid: int):
            async with sem:
                try:
                    r = await client.get(MET_API.format(oid))
                    d = r.json() if r.status_code == 200 else None
                    out[oid] = None if d is None else {"gallery": d.get("GalleryNumber") or "",
                                                       "image_small_url": d.get("primaryImageSmall") or None}
                except (httpx.HTTPError, ValueError):
                    out[oid] = None
        await asyncio.gather(*(one(i) for i in ids))
    return out


# --- Researcher ---

researcher = Agent(
    name="Researcher",
    instructions="""\
You search one slice of The Met's on-view collection for a museum tour. Your task names the
visitor's theme, the slice to search (a department, culture, period or idea), and how many
candidates to return.

1. Search with search_objects, trying several short keyword sets and synonyms (the theme's words
   rarely appear literally: for 'power', try 'king', 'pharaoh', 'emperor', 'throne', 'armor', 'crown').
   Use gallery_summary or run_sql to find galleries dense with relevant objects.
2. Call get_object on your best candidates to read their details. Prefer objects that have an image,
   a named maker or a clear story, and highlights. Avoid near-duplicates (ten similar beads).
3. If an object has object_wikipedia or artist_wikipedia, you may read it with get_wikipedia and quote
   one or two short facts that make the stop interesting.
4. Reply with JSON only, no prose:
   {"slice": "...", "candidates": [{"object_id": 123, "title": "...", "gallery": "...",
     "why_it_fits": "one sentence tying it to the theme, from the record",
     "evidence": [{"fact": "...", "source": "met:123" or "wikipedia:Article Title"}]}],
    "gaps": "what you looked for and could not find, or empty"}
Every fact must come from a tool result, with its source. Never invent objects, IDs or galleries.
If the slice has nothing that fits, return an empty candidates list and say so in gaps.""",
    model=RESEARCH_MODEL,
    model_settings=SETTINGS,
    tools=[search_objects, get_object, gallery_summary, run_sql, get_wikipedia],
)


@function_tool
async def research(ctx: RunContextWrapper[Run], theme: str, slices: list[str], candidates_per_slice: int = 4) -> str:
    """Send Researchers out in parallel, one per slice of the museum, each in a fresh context.
    Waits for all of them and returns their candidates and gaps.

    Args:
        theme: The visitor's interests and constraints, in one or two sentences.
        slices: 2 to 5 slices to search, e.g. ['Egyptian Art: cats and lions', 'Asian Art: tigers and cranes'].
        candidates_per_slice: How many candidates each Researcher returns.
    """
    run = ctx.context
    slices = slices[:MAX_RESEARCHERS]

    async def one(slice_: str):
        run.researchers += 1
        agent = researcher.clone(name=f"Researcher {run.researchers}")
        prompt = f"Theme: {theme}\nYour slice: {slice_}\nReturn up to {candidates_per_slice} candidates."
        try:
            result = await Runner.run(agent, prompt, context=run, hooks=HOOKS, max_turns=RESEARCHER_MAX_TURNS)
            return {"slice": slice_, "agent": agent.name, "findings": str(result.final_output)}
        except Exception as e:  # one Researcher failing must not sink the tour
            return {"slice": slice_, "agent": agent.name, "error": f"{type(e).__name__}: {str(e)[:200]}"}

    return _dump(await asyncio.gather(*(one(s) for s in slices)))


# --- Writer ---

writer = Agent(
    name="Writer",
    instructions="""\
You write the visitor-facing text for a museum guide at The Met, from the evidence you are given
and nothing else.

For a tour: a title, one or two sentences on the thread connecting the stops, then each stop in
the given order as:
### <n>. <Title> — Gallery <number>
*<artist or culture>, <date>* · about <minutes> min in
Two to four sentences: what to look at, and why it belongs on this tour. End each sentence that
states a fact with its source tag: [met:<object_id>] or [wikipedia:<Article Title>].
Then a short "Before you go" list with the route notes you were given (approximate walking times,
removed stops, optional stops), and anything the data could not tell you.

For a single object or a question: a short, direct answer with source tags on every fact.

Rules: use only facts in the evidence. If the evidence does not say something, do not say it.
Plain, warm, concrete language; no hype words ("stunning", "masterpiece", "testament").""",
    model=WRITER_MODEL,
    model_settings=SETTINGS,
)


@function_tool
async def write_tour(ctx: RunContextWrapper[Run], request: str, route_json: str, evidence_json: str) -> str:
    """Have the Writer write the final tour from the planned route and the Researchers' evidence.
    Returns the tour text: reply with it as it is.

    Args:
        request: The visitor's request and constraints.
        route_json: The JSON that plan_route returned.
        evidence_json: The candidates and evidence for the chosen stops (from research), as JSON.
    """
    prompt = f"Visitor request: {request}\n\nRoute (in walking order):\n{route_json}\n\nEvidence:\n{evidence_json}"
    result = await Runner.run(writer, prompt, context=ctx.context, hooks=HOOKS, max_turns=2)
    return str(result.final_output)


# --- Lead ---

lead = Agent(
    name="Guide",
    instructions="""\
You are a guide to The Met Fifth Avenue for visitors. You work only from tools: an on-view
snapshot of the Met's collection, Wikipedia articles linked from it, and the Met's live API.

Decide what the visitor needs:

A. A tour ("I have two hours and love Japan"):
   - If the request is too vague to plan (no interests at all, e.g. "show me cool stuff"), ask one
     short question about their interests and time, and stop.
   - Otherwise call research once with 2 to 5 slices that cover the theme across different
     departments. Then pick 8 to 12 stops (fewer for under an hour) from the candidates: varied,
     on theme, not crowded into one gallery.
   - If the findings leave a gap (a slice came back empty, or fewer than 6 good stops), call
     research again with new slices. At most 3 research calls in total.
   - Call plan_route with the chosen object IDs, the visitor's start gallery and time budget.
   - Call write_tour with the request, plan_route's JSON, and the evidence for the chosen stops.
     Reply with the tour exactly as write_tour returns it.

B. "What is this?" (a label photo, or an accession number / title they typed):
   - Read the accession number, title and artist from the label. Call find_by_accession with the
     title and artist as hints (or find_by_title if there is no number).
   - Name an object only if the status is exact, corrected or near_confirmed. If it is ambiguous,
     mismatch or not_found, say what you read and ask for the title or a clearer photo.
   - Then call get_object (and get_wikipedia for its linked articles) and answer briefly with
     source tags [met:<id>] / [wikipedia:<title>]. Offer what to see next nearby.
   - If they are on a tour and ask what is next, re-plan with plan_route from their gallery.

C. Questions about the collection ("how many Monets are on view?", "which gallery has the most
   armor?"): use run_sql or search_objects, and answer with the numbers and source tags.

Always:
- Every fact you state comes from a tool result. Cite [met:<id>] for objects and say "in the Met's
  on-view data as of <date from snapshot_info>" for counts.
- Say plainly when the data cannot answer: crowds, opening hours, loans and special exhibitions
  (not in this data), objects not on view, what a label says beyond the record.
- Keep replies short; visitors are standing in a museum.""",
    model=LEAD_MODEL,
    model_settings=SETTINGS,
    tools=[research, plan_route, write_tour, find_by_accession, find_by_title, get_object, search_objects,
           gallery_summary, run_sql, snapshot_info, get_wikipedia],
)


async def chat(history: list, message: str | list) -> tuple[str, list[dict], list]:
    """Run one visitor turn. Returns (reply, tool_calls, new history)."""
    run = Run()
    result = await Runner.run(lead, history + [{"role": "user", "content": message}], context=run, hooks=HOOKS,
                              max_turns=LEAD_MAX_TURNS)
    return str(result.final_output), run.tool_calls, result.to_input_list()
