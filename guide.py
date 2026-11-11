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
from agents.exceptions import MaxTurnsExceeded
from agents.extensions.models.litellm_model import LitellmModel

import citations
import met_tools
import route
import wikipedia

set_tracing_disabled(True)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LEAD_MODEL = LitellmModel(model=os.environ.get("LEAD_MODEL", "vertex_ai/gemini-3.5-flash"), api_key="unused")
RESEARCH_MODEL = LitellmModel(model=os.environ.get("RESEARCH_MODEL", "vertex_ai/gemini-3.5-flash"), api_key="unused")
WRITER_MODEL = LitellmModel(model=os.environ.get("WRITER_MODEL", "vertex_ai/gemini-3.5-flash"), api_key="unused")
_extra = {"vertex_location": "global", "timeout": 90, "num_retries": 2}
if PROJECT:
    _extra["vertex_project"] = PROJECT
SETTINGS = ModelSettings(extra_args=_extra)
# Researchers make many quick tool calls: little thinking keeps a tour fast. Lead and Writer think fully.
RESEARCH_SETTINGS = ModelSettings(extra_args={**_extra, "reasoning_effort": os.environ.get("RESEARCH_EFFORT", "minimal")})

MAX_RESEARCHERS = 5
LEAD_MAX_TURNS = 20
RESEARCHER_MAX_TURNS = 8
MET_API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"


# --- Run state: the tool-call log every agent writes to, returned by /chat ---


class Run:
    def __init__(self):
        self.tool_calls: list[dict] = []
        self.researchers = 0
        self.storytellers = 0


class LogHooks(RunHooks):
    """Record every tool call, by any agent, as {agent, name, args, result} for /chat's tool_calls."""

    async def on_tool_end(self, context, agent, tool, result) -> None:
        try:
            args = json.loads(getattr(context, "tool_arguments", "") or "{}")
        except json.JSONDecodeError:
            args = {"raw": getattr(context, "tool_arguments", "")}
        text = result if isinstance(result, str) else json.dumps(result, default=str)
        # The page draws the tour from plan_route's result, so that one is kept whole
        limit = 30_000 if tool.name == "plan_route" else 4000
        context.context.tool_calls.append(
            {"agent": agent.name, "name": tool.name, "args": args, "result": text[:limit]})


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
    """Read an English Wikipedia article by exact title: one from get_object's object_wikipedia or
    artist_wikipedia fields, or one that search_wikipedia found.

    Args:
        title: The article title, e.g. 'Wheat Field with Cypresses' or 'Ptolemaic Kingdom'.
    """
    return _dump(wikipedia.fetch(title))


@function_tool
def search_wikipedia(query: str) -> str:
    """Search English Wikipedia for article titles, with a short snippet of each. Use it to find
    background articles about an object's culture, period, material, technique or subject.

    Args:
        query: A few words from the object's record, e.g. 'Ptolemaic Egypt bronze cat statuette'.
    """
    return _dump(wikipedia.search(query))


@function_tool
async def plan_route(object_ids: list[int], extra_ids: list[int] | None = None, start_gallery: str = "",
                     minutes_per_stop: float = 6, budget_minutes: float | None = None) -> str:
    """Order the main stops into a walk through the building and estimate the time; the extras
    continue the same walk after the last main stop, for a visitor with time left. Also checks every
    object against the Met's live API, and drops any that are no longer on view.

    Args:
        object_ids: The main stops, in any order: about one per 10 minutes of the visitor's time.
        extra_ids: 4 to 6 more good stops for a visitor with time left, in any order. The route
            keeps up to 3 that continue the walk without doubling back.
        start_gallery: Where the visitor is now (a gallery number); empty means the main entrance.
        minutes_per_stop: Time to spend at each object.
        budget_minutes: The visitor's total time, if they gave one.
    """
    extra_ids = [i for i in dict.fromkeys(extra_ids or []) if i not in set(object_ids)]
    stops, missing = [], []
    for oid in list(dict.fromkeys(object_ids)) + extra_ids:
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
    extra_set = set(extra_ids)
    result = route.plan([s for s in keep if s["object_id"] not in extra_set], start_gallery, minutes_per_stop,
                        budget_minutes, extras=[s for s in keep if s["object_id"] in extra_set])
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
    headers = {"User-Agent": "docent-ai/0.1 (student course project; educational, non-commercial)"}
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

Budget: at most 6 tool calls, then reply. A short list of good candidates beats a long search.

1. Start with run_sql on the tags column when the theme has a matching subject tag (e.g.
   list_contains(tags, 'Cats'), 'Horses', 'Lions', 'Birds'; see what exists with
   SELECT unnest(tags) t, count(*) ... GROUP BY t). Otherwise use search_objects, trying several
   short keyword sets and synonyms (the theme's words
   rarely appear literally: for 'power', try 'king', 'pharaoh', 'emperor', 'throne', 'armor', 'crown').
   Use gallery_summary or run_sql to find galleries dense with relevant objects.
2. Call get_object on your best 2 or 3 candidates (not every one) to read their details. Prefer objects that have an image,
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
    model_settings=RESEARCH_SETTINGS,
    tools=[search_objects, get_object, gallery_summary, run_sql, get_wikipedia],
)


async def _wrap_up(data) -> str:
    """Out of steps: rather than lose the work, ask the same agent, with no tools left, to answer
    from what it has already found."""
    agent = data.run_data.last_agent.clone(tools=[])
    history = data.run_data.history + data.run_data.output + [{
        "role": "user", "content": "Your step budget is used up. Reply now with the JSON, using only "
                                   "what your tool results already showed. Put what you could not check in gaps."}]
    result = await Runner.run(agent, history, context=data.context.context, max_turns=1)
    return str(result.final_output)


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
            result = await Runner.run(agent, prompt, context=run, hooks=HOOKS, max_turns=RESEARCHER_MAX_TURNS,
                                      error_handlers={"max_turns": _wrap_up})
            return {"slice": slice_, "agent": agent.name, "findings": str(result.final_output)}
        except MaxTurnsExceeded:
            return {"slice": slice_, "agent": agent.name,
                    "error": "Ran out of steps before answering. Try a narrower slice."}
        except Exception as e:  # one Researcher failing must not sink the tour
            return {"slice": slice_, "agent": agent.name, "error": f"{type(e).__name__}: {str(e)[:200]}"}

    return _dump(await asyncio.gather(*(one(s) for s in slices)))


# --- Storyteller ---

STORYTELLER_MAX_TURNS = 6

storyteller = Agent(
    name="Storyteller",
    instructions="""\
You tell the story of one object at The Met to a visitor who is curious but not an expert: they
don't know the periods, techniques or terms, and want to understand what they are looking at and
why it matters. You get the object's Met record and anything a Researcher already found.

Budget: at most 4 tool calls.
1. If the record has object_wikipedia or artist_wikipedia, read that article with get_wikipedia.
2. Find one or two background articles that explain the context a non-expert is missing: the
   culture or period (e.g. 'Ptolemaic Kingdom'), the material or technique (e.g. 'Sancai'), or the
   subject (e.g. 'Cats in ancient Egypt'). Use search_wikipedia with words from the record, then
   read the best match with get_wikipedia. Use an article only if it is clearly about this object's
   own culture, period, material, maker or subject; skip it otherwise.
3. Reply with JSON only, no prose:
   {"object_id": 123,
    "story": "80 to 120 words in plain language: what it is, the context that makes it make sense,
              and why it matters. Explain any term the visitor may not know, in a few words.",
    "look_for": "what to notice in front of the object, as a phrase that follows 'Look for',
                 e.g. 'the metal pins under the base, used to mount it'",
    "sources_read": ["Wikipedia titles you used"],
    "gaps": "what you could not find, or empty"}

Rules:
- Every fact comes from the record or an article you read in this task. Your own knowledge does not
  count: if neither says it, leave it out, however well known it is. A background article supports
  general context (what the Ptolemaic period was), never a claim about this particular object that
  the record does not make.
- End each sentence that states a fact with its tag: [met:<object_id>] for the record,
  [wikipedia:<Exact Article Title>] for an article.
- look_for must describe only what the record says the object is or shows.
- Warm and concrete, like a good docent; no hype words ("stunning", "masterpiece", "famous",
  "testament", "vibrant", "incredible").""",
    model=WRITER_MODEL,
    model_settings=SETTINGS,
    tools=[get_wikipedia, search_wikipedia],
)


async def _tell(run: Run, object_id: int, context: str) -> dict:
    """One Storyteller, in a fresh context, for one object. Never raises: a failed story is a gap."""
    record = met_tools.get_object(object_id)
    if "error" in record:
        return {"object_id": object_id, "error": record["error"]}
    run.storytellers += 1
    agent = storyteller.clone(name=f"Storyteller {run.storytellers}")
    prompt = f"{context}\n\nMet record:\n{_dump(record)}"
    try:
        result = await Runner.run(agent, prompt, context=run, hooks=HOOKS, max_turns=STORYTELLER_MAX_TURNS,
                                  error_handlers={"max_turns": _wrap_up})
        return {"object_id": object_id, "agent": agent.name, "story": str(result.final_output)}
    except Exception as e:  # one story failing must not sink the tour
        return {"object_id": object_id, "agent": agent.name, "error": f"{type(e).__name__}: {str(e)[:200]}"}


async def tell_stories(run: Run, object_ids: list[int], request: str, evidence_json: str) -> list[dict]:
    """A Storyteller per stop, all in parallel."""
    def context_for(oid: int) -> str:
        found = [c for c in _candidates(evidence_json) if str(c.get("object_id")) == str(oid)]
        return (f"Visitor request: {request}\n"
                + (f"What the Researcher found:\n{_dump(found[0])}" if found else ""))
    return list(await asyncio.gather(*(_tell(run, oid, context_for(oid)) for oid in object_ids)))


def _candidates(evidence_json: str) -> list[dict]:
    """Pull candidate objects out of whatever shape the Lead passed as evidence."""
    out = []
    def walk(x):
        if isinstance(x, dict):
            if "object_id" in x:
                out.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x.lstrip().startswith(("{", "[")):
            try:
                walk(json.loads(x))
            except ValueError:
                pass
    try:
        walk(json.loads(evidence_json))
    except ValueError:
        pass
    return out


@function_tool
async def tell_story(ctx: RunContextWrapper[Run], object_id: int, question: str = "") -> str:
    """Have a Storyteller explain one object in plain language, with Wikipedia background on its
    culture, period or material. Use it for "what is this?" questions; pass its result to write_answer.

    Args:
        object_id: The Met object ID.
        question: What the visitor asked, if anything specific.
    """
    return _dump(await _tell(ctx.context, object_id, f"Visitor question: {question or 'What is this?'}"))


# --- Writer ---

writer = Agent(
    name="Writer",
    instructions="""\
You write the visitor-facing text for a museum guide at The Met, from the evidence you are given
and nothing else. Visitors are curious but not experts: plain words, and a few words of explanation
for any term they may not know.

For a tour: a title, one or two sentences on the thread connecting the stops, then each stop in
the given order as:
### <n>. <Title> — Gallery <number>
*<artist or culture>, <date>* · about <minutes> min in
The stop's story from its Storyteller, kept close to as written with its source tags (you may trim
it, join it to the tour's thread in a few words, or drop a sentence; never add facts). Then a line
"Look for: ..." from the Storyteller's look_for. If a stop has no story, write two or three sentences
from the Researcher's evidence. End each sentence that states a fact with its source tag:
[met:<object_id>] or [wikipedia:<Article Title>].
After the main stops, if the route has extras: a heading "## Extras, if you have time", then each
extra in the given order, numbered on from the main stops (after stop 6 comes 7), in the same
format as a main stop: they continue the same walk.
Then a short "Before you go" list with the route notes you were given (approximate walking times,
removed stops, optional stops), and anything the data could not tell you.

For a single object or a question: a short, direct answer with source tags on every fact.

Rules:
- Use only facts in the evidence. Your own knowledge of art history does not count as evidence:
  if the evidence does not say it, leave it out, however well known it is.
- Every sentence that states a fact ends with its tag. Tag objects by the object_id in the evidence.
- Counts and other results of a query (how many, which galleries) take one [data] tag instead of a
  tag per object, and say the date of the data, e.g. "in the Met's on-view data as of Nov 7, 2026".
  Use data_as_of from snapshot_info as that date.
- Plain, warm, concrete language; no hype words ("stunning", "masterpiece", "famous", "testament",
  "vibrant", "incredible"). No bold labels inside sentences.""",
    model=WRITER_MODEL,
    model_settings=SETTINGS,
)


async def _write(run: Run, prompt: str) -> str:
    """Have the Writer draft, check its citations in code, and let it revise once if they fail."""
    result = await Runner.run(writer, prompt, context=run, hooks=HOOKS, max_turns=2)
    draft = str(result.final_output)
    report = citations.check(draft, run.tool_calls)
    run.tool_calls.append({"agent": "Citation check", "name": "check_citations", "args": {"draft": draft[:500]},
                           "result": _dump(report)})
    if report["ok"]:
        return draft
    fix = (f"{prompt}\n\nYour draft:\n{draft}\n\nA citation check found problems. Fix them: add a tag to each "
           "uncited sentence if the evidence supports it, otherwise cut the sentence; remove or correct unknown "
           f"sources. Reply with the full corrected text only.\n{_dump(report)}")
    result = await Runner.run(writer, fix, context=run, hooks=HOOKS, max_turns=2)
    final = str(result.final_output)
    run.tool_calls.append({"agent": "Citation check", "name": "check_citations", "args": {"draft": final[:500]},
                           "result": _dump(citations.check(final, run.tool_calls))})
    return final


@function_tool
async def write_tour(ctx: RunContextWrapper[Run], request: str, route_json: str, evidence_json: str) -> str:
    """Write the final tour: a Storyteller per stop (in parallel) explains each object in plain
    language with Wikipedia background, then the Writer assembles the tour. Returns the tour text:
    reply with it as it is.

    Args:
        request: The visitor's request and constraints.
        route_json: The JSON that plan_route returned.
        evidence_json: The candidates and evidence for the chosen stops (from research), as JSON.
    """
    run = ctx.context
    try:
        route_data = json.loads(route_json)
        stops = [s["object_id"] for key in ("stops", "extras", "cloisters_stops") for s in route_data.get(key, [])]
    except (ValueError, KeyError, TypeError, AttributeError):
        stops = [int(c["object_id"]) for c in _candidates(evidence_json) if str(c.get("object_id")).isdigit()]
    stories = await tell_stories(run, list(dict.fromkeys(stops)), request, evidence_json)
    return await _write(run, f"Visitor request: {request}\n\nRoute (in walking order):\n{route_json}"
                             f"\n\nStories, one per stop:\n{_dump(stories)}\n\nResearchers' evidence:\n{evidence_json}")


@function_tool
async def write_answer(ctx: RunContextWrapper[Run], question: str, evidence_json: str) -> str:
    """Have the Writer answer a question about an object or the collection from evidence you gathered
    (tool results: object records, query results, Wikipedia text, and any caveats). Returns the answer:
    reply with it as it is.

    Args:
        question: The visitor's question, plus anything you need to tell them (e.g. a number was misread).
        evidence_json: The tool results the answer rests on, as JSON. Include object_id on every object.
    """
    return await _write(ctx.context, f"Visitor question: {question}\n\nEvidence:\n{evidence_json}")


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
     departments. Then pick from the candidates: main stops, about one per 10 minutes of the
     visitor's time (6 for an hour; 8 if they gave no time), varied, on theme, the strongest ones,
     not crowded into one gallery; and 4 to 6 extras, good stops for a visitor with time to spare
     (the route keeps the ones that continue the walk).
   - Use the Researchers' candidates as they are: do not search the collection yourself during
     a tour. If the findings leave a gap (a slice came back empty or failed, or fewer than 6 good
     stops), call research again with new slices. At most 3 research calls in total.
   - Call plan_route with the main stops as object_ids, the extras as extra_ids, the visitor's
     start gallery and time budget.
   - Call write_tour with the request, plan_route's JSON, and the evidence for the chosen stops.
     Its text goes to the visitor as it is.

B. "What is this?" (a label photo, or an accession number / title they typed):
   - Read the accession number, title and artist from the label. Call find_by_accession with the
     title and artist as hints (or find_by_title if there is no number).
   - Name an object only if the status is exact, corrected or near_confirmed. If it is ambiguous,
     mismatch or not_found, say what you read and ask for the title or a clearer photo.
   - Then call tell_story for it (a plain-language story with Wikipedia background), and
     gallery_summary for its gallery, so you can suggest what to see next nearby.
   - Call write_answer with the question and that evidence (the identification result, the story,
     the gallery summary), and reply with its text as it is.
   - If they are on a tour and ask what is next, re-plan with plan_route from their gallery.

C. Questions about the collection ("how many Monets are on view?", "which gallery has the most
   armor?"): use run_sql or search_objects (include object_id in queries that list objects), call
   snapshot_info for the data's date, then write_answer with the results, and reply with its text.

Always:
- You never write facts yourself: the Writer does, from the evidence you pass it. You may write
  only clarifying questions and "the data can't answer that" replies.
- Every fact comes from a tool result. Cite [met:<id>] for objects and say "in the Met's
  on-view data as of <date from snapshot_info>" for counts.
- Say plainly when the data cannot answer: crowds, opening hours, loans and special exhibitions
  (not in this data), objects not on view, what a label says beyond the record.
- Keep replies short; visitors are standing in a museum.""",
    model=LEAD_MODEL,
    model_settings=SETTINGS,
    # The Writer's checked text is the reply, word for word: the Lead stops as soon as it has it.
    tool_use_behavior={"stop_at_tool_names": ["write_tour", "write_answer"]},
    tools=[research, plan_route, write_tour, write_answer, tell_story, find_by_accession, find_by_title, get_object, search_objects,
           gallery_summary, run_sql, snapshot_info, get_wikipedia],
)


async def chat(history: list, message: str | list) -> tuple[str, list[dict], list]:
    """Run one visitor turn. Returns (reply, tool_calls, new history).

    If the Lead runs out of turns, the visitor gets an honest message and the tool calls so far,
    instead of an error page.
    """
    run = Run()
    turn = history + [{"role": "user", "content": message}]
    try:
        result = await Runner.run(lead, turn, context=run, hooks=HOOKS, max_turns=LEAD_MAX_TURNS)
    except MaxTurnsExceeded:
        reply = ("I ran out of steps before finishing this one. Try narrowing it down (fewer themes, or one "
                 "department), and I'll try again.")
        return reply, run.tool_calls, turn + [{"role": "assistant", "content": reply}]
    return str(result.final_output), run.tool_calls, result.to_input_list()
