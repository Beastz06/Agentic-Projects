"""PRD Drafter agent (C3).

Consumes a DiscoveryFinding (C2) and produces a validated PRD. The model holds
the smallest possible pen: it writes prose and cites source pain points by
index; code maps indices to verified evidence_issue_ids. The model never sees
or types an issue number. All validation failures — structural (Pydantic) or
semantic (issue numbers in prose) — route through one repair loop with a
2-retry budget; exhaustion raises. Each retry emits a telemetry record; the
exhaustion is the only thing that reaches graph state.
"""
import re
import anthropic
from pydantic import ValidationError
import config
from schemas.discovery import DiscoveryFinding
from schemas.prd import PRD
import telemetry

TOOL_NAME = "submit_prd"
MAX_RETRIES = 2
PROSE_ID_PATTERN = re.compile(r"(?i)(?:#|issues?\s+#?)\d{3,}")

PRD_TOOL = {
    "name": TOOL_NAME,
    "description": "Submit the completed Product Requirements Document.",
    "input_schema": PRD.model_json_schema(),
}

SYSTEM_PROMPT = """You are a product manager writing a Product Requirements Document (PRD).

## Input
You receive a DiscoveryFinding: a theme, a numbered list of pain points
clustered from real GitHub issues (each with a cluster name, severity, and
frequency — the count of evidence issues behind it), and a suggested_prd_seed
synthesized by the researcher.

## How to fill each field
- theme: Leave as an empty string — it is set programmatically from the
  finding. Do not author it.
- problem_statement: Expand the suggested_prd_seed into a specific, concrete
  problem statement. Draw on the pain points for substance. Do NOT include
  issue numbers or citations anywhere in the prose.
- target_user: Derive from the personas visible in the pain points. Do not
  invent a user the evidence doesn't support; if the evidence is vague, stay
  general rather than specific-but-fabricated.
- user_stories: Each story must trace to one or more pain points. Write
  persona, action, and value. In source_pain_point_indices, list the numbers
  of the pain points (as numbered in the input) this story is drawn from.
  Leave evidence_issue_ids as an empty list — it is set programmatically.
- acceptance_criteria: Concrete and testable. A reviewer must be able to
  answer "did this happen, yes or no?" for each. Ground them in the stories.
  See "Acceptance criteria" below.
- success_metrics: Your judgment. Each needs a name, a precise definition,
  and a numeric target.
- out_of_scope: Your judgment. Name adjacent work deliberately excluded.
- risks: Your judgment. If the finding is thin (few pain points, weak
  evidence), say so here as a risk — a thin PRD should admit it.

## Acceptance criteria
Write each criterion so it describes one observable change and nothing else.
Three things break that.

- Unobservable slots. Given, When, and Then must each name a concrete state, a
  concrete action, and a concrete result. Words like "properly", "as expected",
  or "a user" leave the reader nothing to look at.
- Welded results. A criterion asserting two independent results has no defined
  answer when one holds and the other does not.
- Duplicate coverage. Two criteria that come down to the same behaviour spend
  two slots on one thing.

Splitting, worked. This criterion welds two results:

  Given a parcel is held in a locker past its collection window,
  when the retention period expires,
  then the parcel is returned to the depot and the recipient is notified by SMS.

Return and notification are independent — either can occur without the other.
As two criteria:

  Given a parcel is held in a locker past its collection window,
  when the retention period expires,
  then the parcel moves to the depot return queue.

  Given a parcel has moved to the depot return queue,
  when the transfer is recorded,
  then an SMS is sent to the recipient's registered number.

Splitting raises the criterion count. That is the correct outcome, not scope
creep.

## Grounding discipline (absolute)
- Never write an issue number anywhere in the PRD. Not in prose, not in lists.
- Quantify only with numbers derivable from the finding, such as pain-point
  frequency counts. Never state percentages or rates — the finding contains
  no denominators.
- Every user story's source_pain_point_indices must reference only pain-point
  numbers that appear in the input.
- If the finding has no pain points, produce a minimal PRD: expand the seed
  into the problem statement, leave user_stories empty, and flag the missing
  evidence in risks. A thin PRD from thin evidence is correct; a rich PRD
  from thin evidence is fabrication.

## Quality bar — one worked example
The following example is from an unrelated consumer product. Match its level
of specificity and testability. Do NOT reuse its content, personas, metrics,
or domain in any way.

Example input theme: "substitutions" (grocery delivery app)
Example output PRD:
{
  "theme": "",
  "problem_statement": "When an ordered item is out of stock, shoppers substitute on gut feel. Across 14 support threads last quarter, wrong-size swaps, wrong brand-tier swaps, and dietary conflicts (dairy substituted into a dairy-free order) were the three most repeated complaints. There is no way for a customer to state substitution preferences before checkout, and no way for a shopper to see them.",
  "target_user": "Weekly grocery-delivery customers with consistent dietary or brand constraints",
  "user_stories": [
    {
      "persona": "a customer with a dairy allergy",
      "action": "mark my whole order as no-dairy-substitutions",
      "value": "a stockout never becomes a health risk",
      "source_pain_point_indices": [1],
      "evidence_issue_ids": []
    },
    {
      "persona": "an in-store shopper",
      "action": "see the customer's substitution rules on the item card before I pick a replacement",
      "value": "I stop guessing and my refund rate drops",
      "source_pain_point_indices": [1, 2],
      "evidence_issue_ids": []
    }
  ],
  "acceptance_criteria": [
    {"given": "a customer has set 'no dairy' as an order-level rule", "when": "the shopper opens any out-of-stock item in that order", "then": "dairy-containing suggestions are excluded from the replacement list"},
    {"given": "a customer has not set any substitution preference", "when": "the shopper proposes a replacement for an out-of-stock item", "then": "a push notification carrying approve and reject actions reaches the customer within 60 seconds of that proposal"},
    {"given": "a customer rejects a proposed substitution", "when": "the shopper confirms the rejection", "then": "the item is refunded in the same transaction"},
    {"given": "a rejected substitution has been refunded", "when": "the order is closed", "then": "the item is marked 'do not substitute' on the customer's profile"}
  ],
  "success_metrics": [
    {"name": "substitution complaints", "definition": "count of substitution-related refunds plus support tickets per week", "target": "under 20 per week within two release cycles"},
    {"name": "preference adoption", "definition": "count of active weekly customers with at least one substitution rule saved", "target": "10,000 customers within 90 days of launch"}
  ],
  "out_of_scope": ["real-time chat between shopper and customer", "automatic dietary inference from purchase history"],
  "risks": [
    {"description": "Shoppers may ignore on-screen rules under time pressure, making the feature look broken even when adoption is high", "severity": "medium"}
  ]
}
"""


def _build_user_prompt(finding: DiscoveryFinding, feedback: str | None = None) -> str:
    if finding.pain_points:
        blocks = []
        for i, pp in enumerate(finding.pain_points, start=1):
            blocks.append(
                f"Pain point {i}: {pp.cluster} "
                f"(severity: {pp.severity}, frequency: {pp.frequency})"
            )
        pain_section = "\n".join(blocks)
    else:
        pain_section = "(none — the researcher found no coherent pain points)"

    base = (
        f"Theme: {finding.theme}\n\n"
        f"Pain points (numbered — cite these numbers in "
        f"source_pain_point_indices):\n{pain_section}\n\n"
        f"Suggested PRD seed:\n{finding.suggested_prd_seed}\n\n"
    )
    if feedback:
        base += (
            f"A human reviewer rejected a previous draft of this PRD "
            f"with the following revision instruction. Address it directly:\n"
            f"{feedback}\n\n"
        )
    return base + "Write the PRD."


def _prose_fields(prd: PRD) -> list[tuple[str, str]]:
    """Every model-written prose string in the PRD, as (field_path, text) pairs."""
    pairs = [
        ("problem_statement", prd.problem_statement),
        ("target_user", prd.target_user),
    ]
    for i, s in enumerate(prd.user_stories, start=1):
        pairs += [
            (f"user_stories[{i}].persona", s.persona),
            (f"user_stories[{i}].action", s.action),
            (f"user_stories[{i}].value", s.value),
        ]
    for i, ac in enumerate(prd.acceptance_criteria, start=1):
        pairs += [
            (f"acceptance_criteria[{i}].given", ac.given),
            (f"acceptance_criteria[{i}].when", ac.when),
            (f"acceptance_criteria[{i}].then", ac.then),
        ]
    for i, m in enumerate(prd.success_metrics, start=1):
        pairs += [
            (f"success_metrics[{i}].name", m.name),
            (f"success_metrics[{i}].definition", m.definition),
            (f"success_metrics[{i}].target", m.target),
        ]
    for i, item in enumerate(prd.out_of_scope, start=1):
        pairs.append((f"out_of_scope[{i}]", item))
    for i, r in enumerate(prd.risks, start=1):
        pairs.append((f"risks[{i}].description", r.description))
    return pairs


def _attach_evidence(prd: PRD, finding: DiscoveryFinding) -> PRD:
    """Code-set citation grounding. Unconditional overwrite: whatever the
    model wrote in evidence_issue_ids is discarded. Out-of-range indices are
    stripped, mirroring C2's strip-invented-citations pattern."""
    n = len(finding.pain_points)
    for story in prd.user_stories:
        valid = [i for i in story.source_pain_point_indices if 1 <= i <= n]
        story.source_pain_point_indices = valid
        ids: list[int] = []
        for i in valid:
            for issue_id in finding.pain_points[i - 1].evidence_issue_ids:
                if issue_id not in ids:
                    ids.append(issue_id)
        story.evidence_issue_ids = ids
    return prd


def draft_prd(finding: DiscoveryFinding, feedback: str | None = None) -> PRD:
    """Draft a PRD from a DiscoveryFinding, with validated grounding.
    feedback: optional human revision instruction from the approval gate; appended to the drafting prompt when present.

    Raises RuntimeError if the model produces no tool_use block or fails
    validation (structural or semantic) after MAX_RETRIES repair attempts.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": _build_user_prompt(finding, feedback)}]
    last_error = "unknown"

    for attempt in range(1 + MAX_RETRIES):
        response = client.messages.create(
            model=config.AGENT_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=[PRD_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=messages,
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise RuntimeError("Model returned no tool_use block despite forced tool_choice.")

        error_text = None
        defect_origin = None
        prd = None
        try:
            # Stamp intrinsic identity at construction: model-emitted theme is
            # discarded, code sets it from the finding. Inside the loop so every
            # attempt — including repairs — builds a themed PRD; there is no
            # window where an identity-less PRD exists.
            prd = PRD.model_validate({**tool_use.input, "theme": finding.theme})
        except ValidationError as e:
            error_text = str(e)
            defect_origin = type(e).__name__

        if prd is not None:
            hits = []
            for field, text in _prose_fields(prd):
                found = PROSE_ID_PATTERN.findall(text)
                if found:
                    hits.append(f"{field}: {found}")
            if hits:
                error_text = (
                        "The PRD contains issue-number references in prose fields:\n"
                        + "\n".join(hits)
                        + "\nRemove them from the prose. Change nothing else."
                )
                defect_origin = telemetry.DEFECT_PROSE_ID_LEAK
                prd = None

        if prd is not None:
            return _attach_evidence(prd, finding)

        last_error = error_text
        telemetry.repair_fire(
            telemetry.drafter_log,
            attempt=attempt + 1,
            defect_origin=defect_origin,
            detail=error_text,
        )
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
                            f"Your submitted PRD failed validation:\n\n{error_text}\n\n"
                            f"Resubmit the full PRD. Fix only what the error names; "
                            f"change nothing else."
                        ),
                    }
                ],
            },
        ]

    raise RuntimeError(
        f"PRD failed validation after {1 + MAX_RETRIES} attempts. Last error:\n{last_error}"
    )
