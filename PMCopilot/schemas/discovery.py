"""Discovery schemas (C2).

PainPoint and DiscoveryFinding define the data contract produced by the
Discovery Researcher agent and consumed by the PRD Drafter. They live here,
separate from agent code, so consumers import the type without dragging the
agent's runtime dependencies.
"""
from typing import Literal
from pydantic import BaseModel, Field, computed_field


class PainPoint(BaseModel):
    cluster: str
    evidence_issue_ids: list[int] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"]

    @computed_field
    @property
    def frequency(self) -> int:
        return len(self.evidence_issue_ids)


class DiscoveryFinding(BaseModel):
    theme: str
    pain_points: list[PainPoint] = Field(default_factory=list)
    # Intent: a 1–2 sentence handoff (~500 chars). Enforced softly in
    # research() at the orchestration layer, not as a hard schema constraint —
    # a good finding must never be discarded over a creative-field length cap.
    suggested_prd_seed: str
