"""Order tour stops into a sensible walk through the Met's Fifth Avenue building.

The Met publishes gallery numbers but no map data, so this uses an approximate model of the
building: a gallery's hundreds block is its wing (100s Egyptian/Greek and Roman, 600s European
paintings, ...), and each block sits on a known main floor. Walking cost grows from same gallery,
to the same wing, to another wing on the same floor, to another floor. It is a rough model, and
every route says so.
"""

import itertools
import re

# Main floor of each hundreds block of gallery numbers at the Met Fifth Avenue (approximate).
# 0xx galleries are The Met Cloisters, a separate building in Fort Tryon Park.
FLOOR_OF_BLOCK = {1: 1, 2: 2, 3: 1, 4: 2, 5: 1, 6: 2, 7: 1, 8: 2, 9: 1}
WING_OF_BLOCK = {
    1: "Egyptian / Greek and Roman", 2: "Asian Art", 3: "Medieval, Arms and Armor, Africa/Oceania/Americas",
    4: "Islamic and Ancient Near Eastern", 5: "European Sculpture and Decorative Arts",
    6: "European Paintings", 7: "The American Wing", 8: "19th- and early 20th-century European",
    9: "Modern and Contemporary, Lehman Collection",
}
MINUTES_PER_COST = 1.0  # one unit of walking cost is about a minute on foot
ENTRANCE = "entrance"  # the Great Hall on Fifth Avenue, floor 1


def gallery_key(gallery: str) -> tuple[int, int] | None:
    """'822' -> (8, 822). None for galleries without a number (e.g. 'in Great Hall')."""
    m = re.fullmatch(r"0*(\d+)", str(gallery).strip())
    if not m:
        return None
    n = int(m.group(1))
    return (n // 100 if n >= 100 else 0, n)


def is_cloisters(gallery: str) -> bool:
    key = gallery_key(gallery)
    return key is not None and key[0] == 0


def walk_cost(a: str, b: str) -> float:
    """Approximate minutes to walk from gallery a to gallery b."""
    if a == b:
        return 0.5
    if ENTRANCE in (a, b):
        other = b if a == ENTRANCE else a
        key = gallery_key(other)
        if key is None:
            return 2
        return 3 if FLOOR_OF_BLOCK.get(key[0], 1) == 1 else 7
    ka, kb = gallery_key(a), gallery_key(b)
    if ka is None or kb is None:
        return 5  # a named space (e.g. 'in Great Hall'): assume a moderate walk
    if (ka[0] == 0) != (kb[0] == 0):
        return 120  # The Cloisters is a separate building uptown
    if ka[0] == kb[0]:
        return 1 + min(abs(ka[1] - kb[1]) / 8, 3)
    same_floor = FLOOR_OF_BLOCK.get(ka[0]) == FLOOR_OF_BLOCK.get(kb[0])
    return 6 if same_floor else 9


def _path_cost(order: list[str], start: str) -> float:
    return sum(walk_cost(x, y) for x, y in zip([start] + order, order))


def order_galleries(galleries: list[str], start: str = ENTRANCE) -> list[str]:
    """Shortest visiting order (exact for up to 8 galleries, else nearest-neighbour plus 2-opt)."""
    unique = list(dict.fromkeys(galleries))
    if len(unique) <= 8:
        return list(min(itertools.permutations(unique), key=lambda p: _path_cost(list(p), start)))
    order, left, here = [], set(unique), start
    while left:
        here = min(left, key=lambda g: (walk_cost(here, g), g))
        order.append(here)
        left.remove(here)
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 2, len(order) + 1):
                candidate = order[:i] + order[i:j][::-1] + order[j:]
                if _path_cost(candidate, start) < _path_cost(order, start) - 1e-9:
                    order, improved = candidate, True
    return order


def plan(stops: list[dict], start_gallery: str = "", minutes_per_stop: float = 6, budget_minutes: float | None = None) -> dict:
    """Order stops ({object_id, gallery, ...}) into a walk and estimate its time.

    Stops in the same gallery are kept together. If a time budget is given and the walk runs over,
    the last stops are marked as optional rather than silently dropped.
    """
    start = start_gallery.strip() or ENTRANCE
    main = [s for s in stops if not is_cloisters(s["gallery"])]
    cloisters = [s for s in stops if is_cloisters(s["gallery"])]
    order = order_galleries([s["gallery"] for s in main], start)
    route, minutes, here = [], 0.0, start
    for g in order:
        walk = walk_cost(here, g) * MINUTES_PER_COST
        for k, s in enumerate(x for x in main if x["gallery"] == g):
            minutes += (walk if k == 0 else 0) + minutes_per_stop
            key = gallery_key(g)
            route.append({**s, "walk_minutes_before": round(walk if k == 0 else 0, 1),
                          "arrive_after_minutes": round(minutes - minutes_per_stop, 1),
                          "floor": FLOOR_OF_BLOCK.get(key[0]) if key else None,
                          "wing": WING_OF_BLOCK.get(key[0]) if key else None})
        here = g
    over = budget_minutes is not None and minutes > budget_minutes
    if over:
        running = 0.0
        for r in route:
            running = r["arrive_after_minutes"] + minutes_per_stop
            r["optional"] = running > budget_minutes
    notes = ["Walking times come from an approximate model of the building (gallery numbers grouped "
             "into wings and floors), not from a real floor plan."]
    if cloisters:
        notes.append(f"{len(cloisters)} stop(s) are at The Met Cloisters, a separate building in Fort Tryon "
                     "Park; they are listed apart and not included in the walk.")
    if over:
        notes.append(f"The walk takes about {minutes:.0f} min, over the {budget_minutes:.0f} min budget; "
                     "the last stops are marked optional.")
    return {"start": start, "total_minutes": round(minutes), "stops": route,
            "cloisters_stops": cloisters, "notes": notes}
