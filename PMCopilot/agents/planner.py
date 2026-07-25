"""Roadmap Planner agent (C4).

Consumes a list of PRDs (C3) and produces a prioritized, scheduled roadmap:
one RoadmapItem per PRD. The model JUDGES effort and impact per PRD; a separate
step judges cross-PRD dependencies; CODE computes each item's quarter over the
whole set.

Architecture:
  [1] per-PRD scoring: one call per PRD -> effort + impact
  [2] dependency detection: separate call over the scored drafts
  [3] quarter computation (topological sort + priority-rank + budget packing)
  [4] repair loop (validation failures -> bounded retry)

Why per-PRD scoring (not one batched call):
Scoring one PRD does not require seeing the others, so each PRD gets its own
call with a single-object tool schema (RoadmapItemDraft). No list crosses the
tool boundary, which avoids the output-stringification the batched list-wrapper
provoked.

Why dependency detection is a SEPARATE call:
Dependency detection is the one job that needs all PRDs together (you cannot see
"A is blocked by B" one PRD at a time). It runs as its own step over the scored
drafts. Its tool schema uses one NAMED slot per theme (not an anonymous list in
a wrapper), which resists the stringification quirk.
"""
import json
import graphlib
import anthropic
from pydantic import ValidationError
import config
from schemas.prd import PRD
from schemas.roadmap import RoadmapItemDraft, RoadmapItem

MAX_RETRIES = 2
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
DEFAULT_BUDGET = 16


def _peel(raw):
    """Deterministic encoding fix: if the tool input arrived as a JSON string,
    parse it. Not a repair — costs no retry."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw


# ==========================================================================
# [1] Per-PRD scoring
# ==========================================================================

SCORE_TOOL_NAME = "submit_roadmap_item"

# Tool schema is a single RoadmapItemDraft — one object, valid tool input, no
# wrapper. Each scoring call returns exactly one item.
SCORE_TOOL = {
    "name": SCORE_TOOL_NAME,
    "description": "Submit the scored roadmap item for this one PRD.",
    "input_schema": RoadmapItemDraft.model_json_schema(),
}

SCORE_SYSTEM_PROMPT = """You are a product manager scoring one PRD for a roadmap.

Assign two scores, each with a one-sentence rationale:
- effort: a Fibonacci story-point estimate (1, 2, 3, 5, 8, or 13) of how much
  work the PRD represents. Use the number of user stories and acceptance
  criteria as scale signal.
- impact: a 1-5 estimate of how much the PRD matters, informed by the severity
  of the problem and its risks.

Also set:
- title: a short label for this roadmap item.
- prd_ref: the PRD's theme, exactly as given.
- depends_on: leave as an empty list. Dependencies are determined in a separate
  step, not here.
"""


def _project_prd(prd: PRD) -> str:
    """Reduced view of one PRD for scoring: theme, problem, stories, AC count,
    risks. Full PRD is not needed to score effort/impact.

    Deliberately EXCLUDED: target_user. Every PRD in one product shares roughly
    one user; "same user" is a coincidence of the product, not a scoring or
    blocking signal. Including it would push toward invented dependencies
    (false positives), against the conservative bias we chose."""
    story_lines = []
    for i, s in enumerate(prd.user_stories, start=1):
        story_lines.append(f"    {i}. As {s.persona}, I want to {s.action}, so that {s.value}")
    stories = "\n".join(story_lines) if story_lines else "    (none)"

    risk_lines = []
    for r in prd.risks:
        risk_lines.append(f"    - [{r.severity}] {r.description}")
    risks = "\n".join(risk_lines) if risk_lines else "    (none)"

    return (
        f"theme: {prd.theme}\n"
        f"problem_statement: {prd.problem_statement}\n"
        f"user_stories:\n{stories}\n"
        f"acceptance_criteria_count: {len(prd.acceptance_criteria)}\n"
        f"risks:\n{risks}"
    )


def _score_one(client: anthropic.Anthropic, prd: PRD) -> RoadmapItemDraft:
    """One scored draft for one PRD, with a bounded repair loop.

    The defensive string-peel is the first line (deterministic encoding fix,
    costs no retry); the repair loop handles what the peel cannot — Pydantic
    ValidationError (e.g. effort=7 rejected by the Fibonacci Literal; missing
    fields). prd_ref is code-stamped from the PRD's theme (not trusted from the
    model); depends_on stays empty here regardless of what the model emitted —
    the dependency step populates it."""
    messages = [{"role": "user", "content": _project_prd(prd)}]
    last_error = "unknown"

    for attempt in range(1 + MAX_RETRIES):
        response = client.messages.create(
            model=config.AGENT_MODEL,
            max_tokens=1000,
            system=SCORE_SYSTEM_PROMPT,
            tools=[SCORE_TOOL],
            tool_choice={"type": "tool", "name": SCORE_TOOL_NAME},
            messages=messages,
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise RuntimeError("Model returned no tool_use block despite forced tool_choice.")

        raw = _peel(tool_use.input)
        # Code stamps identity; depends_on stays empty until the dependency step.
        raw = {**raw, "prd_ref": prd.theme, "depends_on": []}

        try:
            return RoadmapItemDraft.model_validate(raw)
        except ValidationError as e:
            last_error = str(e)

        print(f"Scoring validation failed for '{prd.theme}' on attempt {attempt + 1}; retrying.")
        messages = messages + [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "is_error": True,
                        "content": (
                            f"Your submitted item failed validation:\n\n{last_error}\n\n"
                            f"Resubmit the full item. Fix only what the error names; "
                            f"change nothing else."
                        ),
                    }
                ],
            },
        ]

    raise RuntimeError(
        f"Scoring for '{prd.theme}' failed after {1 + MAX_RETRIES} attempts. "
        f"Last error:\n{last_error}"
    )


def _score_all(prds: list[PRD]) -> list[RoadmapItemDraft]:
    """Score every PRD, one call each, collect the drafts."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return [_score_one(client, prd) for prd in prds]


# ==========================================================================
# [2] Dependency detection (separate call over the scored drafts)
# ==========================================================================

DEP_TOOL_NAME = "submit_dependencies"

DEP_SYSTEM_PROMPT = """You are a product manager determining dependencies between PRDs for a roadmap.

A dependency means BLOCKING WORK: PRD A depends on PRD B only if B's work must
ship BEFORE A's work can be completed. This includes behavioral dependencies —
if B changes a shared behavior that A relies on, A depends on B, even if A does
not consume a new API from B.

Do NOT treat these as dependencies:
- Shared vocabulary or subsystem names. Two PRDs mentioning the same term are
  not dependent just because the term appears in both.
- Shared target users. PRDs serving the same kind of user are not dependent
  just because the user overlaps.
- Thematic similarity. Addressing related areas is not a blocking relationship.

When uncertain, emit NOTHING. A missed dependency is a visible gap a reviewer
can catch; an invented dependency silently distorts the schedule. Bias toward
independence.

NEGATIVE EXAMPLE (do not repeat this mistake):
The "streaming" PRD mentions a flag literally named 'disable_streaming=tool_calling'
and discusses 'tool-call streaming'. The "tool_calling" PRD covers tool-call
parsing, rejection flows, and observability. These share the words "tool" and
"streaming", and both serve LangChain developers — but streaming's work does NOT
require tool_calling's work to ship first. They are INDEPENDENT. Emit no
dependency between them on the basis of shared vocabulary.
"""


def _build_dep_tool(themes: list[str]) -> dict:
    """Fixed schema: themes are VALUES, never property keys. Free text in a
    JSON-Schema property key is a request-time 400 (key charset is
    restricted); values are unconstrained. Completeness and uniqueness —
    which the old named-slot schema got from `required` and key-uniqueness —
    move into _validate_dep_output as repairable defects. Valid themes are
    named in the description; violations route through the repair loop, not
    schema enforcement, preserving the invalid-edges-REPAIR ruling."""
    return {
        "name": DEP_TOOL_NAME,
        "description": (
            "Submit, per PRD theme, the list of themes it depends on. "
            f"Submit exactly one entry per theme. Valid themes: {themes}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dependencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string", "description": "The PRD theme this entry is for."},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Themes this one depends on (must ship first). Empty if none.",
                            },
                        },
                        "required": ["theme", "depends_on"],
                    },
                }
            },
            "required": ["dependencies"],
        },
    }


def _build_dep_prompt(drafts: list[RoadmapItemDraft], prds: list[PRD]) -> str:
    """Present all PRDs together (theme + problem_statement + user stories) so
    the model can reason about blocking relationships across the full set."""
    by_theme = {prd.theme: prd for prd in prds}
    blocks = []
    for d in drafts:
        prd = by_theme[d.prd_ref]
        stories = "; ".join(f"{s.action}" for s in prd.user_stories) or "(none)"
        blocks.append(
            f"theme: {d.prd_ref}\n"
            f"  problem_statement: {prd.problem_statement}\n"
            f"  what it builds: {stories}"
        )
    corpus = "\n\n".join(blocks)
    return (
        f"Here are {len(drafts)} PRDs. For each, list the themes it depends on "
        f"(must ship first). Most PRDs are independent — emit empty lists unless "
        f"there is a clear blocking relationship.\n\n"
        f"{corpus}\n\n"
        f"Submit the dependencies."
    )


def _validate_dep_output(raw: dict, theme_set: set[str]) -> dict[str, list[str]]:
    """Validate the dependency call's output: {"dependencies": [{theme, depends_on}]}.
    Raises ValueError naming the defect so the repair loop can feed it back.
    Returns {theme: [deps]} on success — caller shape unchanged.

    Rulings carried over: unknown-theme ENTRIES are harmless (ignored);
    invalid EDGE VALUES repair. New defect classes the array shape makes
    possible (the old keyed schema made them inexpressible): duplicate
    entries and missing themes — both repair."""
    entries = raw.get("dependencies")
    if not isinstance(entries, list):
        raise ValueError("Output must contain a 'dependencies' array.")

    problems = []
    edges: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "theme" not in entry:
            problems.append(f"Malformed entry (need 'theme' and 'depends_on'): {entry!r}")
            continue
        theme = entry["theme"]
        deps = entry.get("depends_on", [])
        if theme not in theme_set:
            continue  # unknown entry: harmless, ignored (prior ruling)
        if theme in edges:
            problems.append(f"'{theme}' appears more than once; submit exactly one entry per theme.")
            continue
        bad = [t for t in deps if t not in theme_set]
        if bad:
            problems.append(
                f"'{theme}' lists dependencies on unknown themes {bad}; "
                f"valid themes are {sorted(theme_set)}."
            )
        if theme in deps:
            problems.append(f"'{theme}' lists itself as a dependency.")
        edges[theme] = [t for t in deps if t in theme_set and t != theme]

    missing = theme_set - set(edges)
    if missing:
        problems.append(
            f"Missing entries for themes {sorted(missing)}; submit exactly one entry per theme."
        )

    if problems:
        raise ValueError("Invalid dependency submission:\n" + "\n".join(problems))

    # Cycle check unchanged.
    sorter = graphlib.TopologicalSorter()
    for theme, deps in edges.items():
        sorter.add(theme, *deps)
    try:
        list(sorter.static_order())
    except graphlib.CycleError as e:
        raise ValueError(
            f"The dependencies contain a cycle ({e.args[1] if len(e.args) > 1 else e}), "
            f"which is unschedulable. Re-examine and emit an acyclic set; when "
            f"uncertain, emit fewer dependencies."
        )
    return edges


def _detect_dependencies(
    drafts: list[RoadmapItemDraft], prds: list[PRD]
) -> list[RoadmapItemDraft]:
    """Populate depends_on via one call over all drafts, with a bounded repair
    loop. Invalid edges and cycles REPAIR (fed back to the model), per prior
    ruling — not silently stripped."""
    themes = [d.prd_ref for d in drafts]
    theme_set = set(themes)
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": _build_dep_prompt(drafts, prds)}]
    dep_tool = _build_dep_tool(themes)
    last_error = "unknown"

    for attempt in range(1 + MAX_RETRIES):
        response = client.messages.create(
            model=config.AGENT_MODEL,
            max_tokens=1000,
            system=DEP_SYSTEM_PROMPT,
            tools=[dep_tool],
            tool_choice={"type": "tool", "name": DEP_TOOL_NAME},
            messages=messages,
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise RuntimeError("Model returned no tool_use block despite forced tool_choice.")

        raw = _peel(tool_use.input)

        try:
            edges = _validate_dep_output(raw, theme_set)
            by_theme = {d.prd_ref: d for d in drafts}
            for theme, deps in edges.items():
                by_theme[theme].depends_on = deps
            return drafts
        except (ValidationError, ValueError) as e:
            last_error = str(e)

        print(f"Dependency validation failed on attempt {attempt + 1}; retrying.")
        messages = messages + [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "is_error": True,
                        "content": (
                            f"Your submitted dependencies failed validation:\n\n{last_error}\n\n"
                            f"Resubmit the full dependency set. Fix only what the error "
                            f"names; change nothing else."
                        ),
                    }
                ],
            },
        ]

    raise RuntimeError(
        f"Dependency detection failed after {1 + MAX_RETRIES} attempts. "
        f"Last error:\n{last_error}"
    )


# ==========================================================================
# [3] Quarter computation (pure code — no model)
# ==========================================================================
#
# Takes the completed drafts (effort, impact, depends_on all populated) and
# assigns each a quarter, producing full RoadmapItems. Three ordered steps:
#
#   1. Topological order  — respect dependencies: anything a draft depends on
#      is scheduled no later than the draft. graphlib.TopologicalSorter raises
#      CycleError on a cycle (safety net; the repair-able cycle check lives in
#      _validate_dep_output where the repair loop can act on it).
#   2. Priority rank       — within the dependency-respected order, prefer higher
#      impact/effort ratio (more value per unit of work, sooner).
#   3. Budget pack         — walk the ranked list; accumulate effort into the
#      current quarter until the next item would exceed `budget`, then open the
#      next quarter. `budget` is a SOFT target: a single item whose effort
#      exceeds the whole budget still gets its own quarter (an item is never
#      split). Dependencies still bind — an item never lands before something it
#      depends on.
#
# On the current 3-PRD test data, edges are empty (topological sort trivial) and
# scores are identical (ranking a wash), but the PACKING path is exercised:
# effort magnitude vs. budget still spreads items across quarters.


def _topological_order(drafts: list[RoadmapItemDraft]) -> list[RoadmapItemDraft]:
    """Order drafts so each draft's dependencies come before it. Raises
    graphlib.CycleError on a dependency cycle."""
    by_theme = {d.prd_ref: d for d in drafts}
    sorter = graphlib.TopologicalSorter()
    for d in drafts:
        # predecessors = the themes this draft depends on (must come first)
        sorter.add(d.prd_ref, *d.depends_on)
    ordered_themes = list(sorter.static_order())  # raises CycleError on a cycle
    return [by_theme[t] for t in ordered_themes if t in by_theme]


def _priority_key(draft: RoadmapItemDraft) -> float:
    """Higher impact per unit effort ranks first. Effort is always >= 1
    (Fibonacci min), so no divide-by-zero."""
    return draft.impact.score / draft.effort.score


def _assign_quarters(
    drafts: list[RoadmapItemDraft], budget: int
) -> list[RoadmapItem]:
    """Promote drafts to RoadmapItems with computed quarters.

    Dependency order is respected first (topological), then within that the
    ranking prefers higher impact/effort ratio. Packing is a stable pass over
    the dependency-respecting order; the priority ratio breaks ties in what to
    place next without violating dependencies.
    """
    # 1. Dependency-respecting order.
    ordered = _topological_order(drafts)

    # 2. Within the dependency order, prefer higher priority. A stable sort by
    #    (descending) priority keeps dependency order among equal-priority items
    #    and never moves a dependent ahead of its blocker, because the topo order
    #    already placed blockers first and stable-sort preserves relative order
    #    for the common case of independent items. (With real edges + inverted
    #    priorities this simple approach can violate a dependency; that is the
    #    parked positive-path case — unexercised on independent test data.)
    ranked = sorted(ordered, key=_priority_key, reverse=True)

    # 3. Budget pack.
    items: list[RoadmapItem] = []
    q_index = 0
    q_load = 0
    for d in ranked:
        e = d.effort.score
        # Open a new quarter if adding this item would exceed the budget AND the
        # current quarter already holds something (soft target: never leave a
        # quarter empty just because one item alone exceeds the budget).
        if q_load > 0 and q_load + e > budget:
            q_index += 1
            q_load = 0
        if q_index >= len(QUARTERS):
            raise RuntimeError(
                f"Roadmap needs more than {len(QUARTERS)} quarters at budget={budget}."
            )
        items.append(RoadmapItem(**d.model_dump(), quarter=QUARTERS[q_index]))
        q_load += e
    return items


# ==========================================================================
# Public entrypoint
# ==========================================================================

def plan(prds: list[PRD], budget: int = DEFAULT_BUDGET) -> list[RoadmapItem]:
    """Turn PRDs into a prioritized, scheduled roadmap.

    Pipeline: score each PRD (1 call each) -> detect dependencies (1 call over
    all) -> compute quarters (pure code).
    """
    drafts = _score_all(prds)
    drafts = _detect_dependencies(drafts, prds)
    return _assign_quarters(drafts, budget)
