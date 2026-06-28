"""Discovery Researcher agent (C2).

Clusters pain points from retrieved GitHub issues into themes, each grounded in
real issue numbers. The anti-hallucination guarantee: every cited issue number
is validated against the issues actually retrieved this call. Invented IDs are
stripped; pain points left with no real evidence are dropped. A thin or empty
finding is a valid result, not an error.
"""
from typing import Literal
import anthropic
from pydantic import BaseModel, Field, computed_field
import config
from rag.retriever import query

RETRIEVAL_K = 8
TOOL_NAME = "report_discovery_finding"


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
    suggested_prd_seed: str = Field(max_length=500)


DISCOVERY_TOOL = {
    "name": TOOL_NAME,
    "description": (
        "Report clustered pain points discovered in the provided GitHub issues, "
        "each grounded in the issue numbers it was drawn from."
    ),
    "input_schema": DiscoveryFinding.model_json_schema(),
}

SYSTEM_PROMPT = (
    "You are a product discovery researcher. Your job is to read a set of "
    "GitHub issues and cluster the pain points they describe into a small number "
    "of coherent themes, then synthesize a one-to-two sentence PRD seed.\n\n"
    "Citation discipline is absolute:\n"
    "- Every pain point must cite the issue numbers it was drawn from, using only "
    "the numbers present in the issues you are given.\n"
    "- Never invent, guess, or infer an issue number that is not shown to you.\n"
    "- If the issues do not support a pain point, do not report it. If none of the "
    "issues describe a coherent pain point for this theme, return an empty list of "
    "pain points. An empty result is acceptable and correct.\n"
    "- Assign severity as low, medium, or high based only on what the issues say."
)


def _build_user_prompt(topic: str, issues: list[dict]) -> str:
    blocks = []
    for rec in issues:
        blocks.append(f"Issue #{rec['number']}:\n{rec['document']}")
    joined = "\n\n---\n\n".join(blocks)
    return (
        f"Theme to research: {topic}\n\n"
        f"Below are the retrieved issues. Cluster their pain points and cite by "
        f"issue number. Use only these issues.\n\n{joined}"
    )


def research(topic: str) -> DiscoveryFinding:
    """Cluster pain points for `topic` from retrieved issues, with validated citations."""
    issues = query(topic, k=RETRIEVAL_K)
    retrieved_ids = {rec["number"] for rec in issues}

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.AGENT_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[DISCOVERY_TOOL],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": _build_user_prompt(topic, issues)}],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise RuntimeError("Model returned no tool_use block despite forced tool_choice.")
    raw = tool_use.input

    finding = DiscoveryFinding(**{**raw, "theme": topic})

    validated: list[PainPoint] = []
    for pp in finding.pain_points:
        real_ids = [i for i in pp.evidence_issue_ids if i in retrieved_ids]
        if real_ids:
            pp.evidence_issue_ids = real_ids
            validated.append(pp)
    finding.pain_points = validated

    return finding
