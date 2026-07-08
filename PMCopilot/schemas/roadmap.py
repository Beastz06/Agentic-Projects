"""Roadmap schemas (C4).

The RoadmapItem is what the Roadmap Planner agent produces from a list of PRDs.
It turns each PRD into a prioritized, scored, scheduled roadmap entry. Consumed
downstream by the Streamlit UI (C8) and the eval harness (C9). Lives in schemas/
so consumers import the data contract without the agent's runtime deps.

Two-schema split (the split IS a design opinion):
- RoadmapItemDraft is what the MODEL emits: only the fields the model must
  JUDGE — title, prd_ref, effort (score+rationale), impact (score+rationale),
  depends_on. The model never sees `quarter`.
- RoadmapItem is the PROMOTED artifact: the draft plus `quarter`, which is
  CODE-COMPUTED (priority-rank + effort-budget packing + dependency-respecting
  topological order) over the WHOLE set. Quarter depends on cross-item/global
  state (every item's effort, the full dependency graph), so it cannot be a
  per-item model field — it is assigned after all drafts exist.

Score layering (schema vs judge):
- A score's VALUE is shape-checked here (Fibonacci for effort, 1-5 for impact):
  an out-of-set value is illegal, not merely poor — reject-and-regenerate, which
  is the schema layer's job.
- A score's RATIONALE is model prose: its QUALITY (is the reasoning convincing?)
  is the judge's job (C9), not constrained here. Binding score+rationale into
  one object makes a bare, unexplained score structurally impossible.

Effort and impact get SEPARATE nested models: their `score` constraints differ
(Fibonacci Literal vs 1-5 range), so a shared model would have to weaken `score`
to a plain int and throw away the per-field guarantee. The constraint drives the
structure.
"""

from typing import Literal
from pydantic import BaseModel, Field


class EffortScore(BaseModel):
    # Fibonacci story-point scale. Literal (not int + prompt) because an
    # off-scale value is ILLEGAL, not poorly-estimated: 7 is not a worse effort
    # than 8, it is not an effort score at all. Closed-set membership is a shape
    # fact -> schema-enforced, reject-and-regenerate on violation.
    score: Literal[1, 2, 3, 5, 8, 13]
    # Why this score. Model prose; quality assessed at the judge layer (C9).
    rationale: str


class ImpactScore(BaseModel):
    # Impact 1-5. Range constraint is a correctness assertion (impact IS 1-5 by
    # definition), not a fabrication trap (the model picks within a range it
    # would pick from anyway).
    score: int = Field(ge=1, le=5)
    rationale: str


class RoadmapItemDraft(BaseModel):
    # ---- The model-output schema: ONLY what the model must judge. ----
    # A short label for the roadmap entry.
    title: str
    # References PRD.theme (intrinsic PRD identity). The pointer, not the PRD.
    prd_ref: str
    # Effort + impact, each score bound to its rationale (no bare scores).
    effort: EffortScore
    impact: ImpactScore
    # Themes of PRDs this one is BLOCKED BY. Populated by the model under a
    # scoped rule (blocking-work incl. behavioral dependency; shared
    # vocabulary/subsystem is NOT a dependency; when uncertain, emit nothing).
    # References PRD.theme values. Default empty: independence is the default.
    depends_on: list[str] = Field(default_factory=list)


class RoadmapItem(RoadmapItemDraft):
    # ---- The promoted artifact: draft + code-computed quarter. ----
    # Inherits every judged field from the draft; adds the one CODE-set field.
    # quarter is computed over the whole set (priority-rank by impact/effort
    # ratio, packed by an effort-point budget, respecting dependency order via
    # topological sort). It is NOT model-judged and never appears in the tool
    # schema the model fills.
    quarter: Literal["Q1", "Q2", "Q3", "Q4"]
