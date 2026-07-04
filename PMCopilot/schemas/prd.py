"""PRD schemas (C3).

The PRD is the artifact the PRD Drafter agent produces from a DiscoveryFinding.
It is consumed downstream by the Roadmap Planner (C4), the Stakeholder
Summarizer (C5), the Streamlit UI (C8), and the eval harness (C9). It lives in
schemas/ — separate from agent code — so every consumer imports the data
contract without dragging the agent's runtime dependencies.

Design stance (the schema IS the product opinion):
- The schema enforces STRUCTURE; the LLM judge evaluates QUALITY. Pydantic
  guarantees a slot exists and has the right shape; whether what fills it is
  *good* (a meaningful metric target, a non-thin user story) is the judge's job.
- "Schema constraints hard, prose soft": closed sets (severity) and structural
  counts (AC min/max) are hard-constrained; model-judged creative fields
  (problem_statement, target_user, definitions) are unconstrained strings.
- Permissive on emptiness: user_stories may be empty (the C2->C3 contract:
  a DiscoveryFinding with pain_points == [] is valid input). The agent, not the
  schema, decides how to handle a thin finding.
"""

from typing import Literal
from pydantic import BaseModel, Field


class UserStory(BaseModel):
    persona: str
    action: str
    value: str
    source_pain_point_indices: list[int] = Field(default_factory=list)
    evidence_issue_ids: list[int] = Field(default_factory=list)


class AcceptanceCriterion(BaseModel):
    # Given/When/Then is enforced by structure: three required fields. The shape
    # IS the constraint — no separate validator needed.
    given: str
    when: str
    then: str


class SuccessMetric(BaseModel):
    name: str
    definition: str
    # A slot for a target. "Quantifiable" cannot be guaranteed by a validator
    # (a digit check is crude; "double activation" has no digit) — its quality
    # is assessed at the judge layer, not here.
    target: str


class Risk(BaseModel):
    description: str
    severity: Literal["low", "medium", "high"]


class PRD(BaseModel):
    # Intrinsic identity — the corpus theme this PRD addresses. Code-set at
    # draft time from DiscoveryFinding.theme (never model-judged); required so
    # a PRD cannot exist without the identity that C4/C5/C6 reference.
    theme: str
    # Grounded (loosely) in DiscoveryFinding.suggested_prd_seed; the model expands.
    problem_statement: str
    # Pure model judgement — nothing in the finding feeds this.
    target_user: str
    # Grounded (strongly) in DiscoveryFinding.pain_points. Permissive: empty is
    # structurally valid (the C2->C3 empty-finding contract). The agent judges
    # thinness.
    user_stories: list[UserStory] = Field(default_factory=list)
    # PRD-level count floor/ceiling. Safe (unlike a per-story or citation floor):
    # ACs are model-authored prose, not facts drawn from a finite grounded pool,
    # so a total of 3 is honestly satisfiable without fabrication pressure.
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=3, max_length=8)
    success_metrics: list[SuccessMetric] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)