"""Stakeholder Summarizer agent (C5).

Consumes the PRDs (C3) and roadmap (C4) and produces ONE StakeholderDigest for
ONE audience per call. Three audiences = three independent calls (the
run-per-audience contract from the roadmap's own signature) — one object per
tool call, no list crosses the tool boundary, no wrapper to stringify.

Prompt architecture — one template, selective tone injection (1a):
Shared discipline (anti-hallucination, key_claims rules, output shape) lives
ONCE in the template; only the TARGET audience's tone block is injected. The
model never sees the other audiences' instructions — the wrong tone is
unrepresentable in context, not merely deselected (same instinct as closed-set
schema membership). Contrast, where useful, is written INTO each block
("unlike an executive summary...") without exposing the other blocks.

Anti-hallucination layering (per failure mode):
- Dangling source ref  -> schema+code (membership: every grounded_in theme
  ∈ input themes; reject-and-regenerate via the repair loop) + prompt
  (coverage: ground every load-bearing claim).
- Invented number      -> prompt (prevent: no figure absent from the input;
  applies to call_to_action with FULL force, not only body) + judge (C9,
  grade-and-keep). Schema cannot see prose; it is not asked to.

key_claims is index-not-generate: it reflects claims already in the prose,
and the prompt affirmatively licenses an empty list for qualitative digests —
honesty is the path of least resistance at both layers.

audience is code-stamped from the call argument (the caller holds the
provenance) — third instance of the stamp idiom after evidence_issue_ids and
PRD.theme.
"""
import json
import anthropic
from pydantic import ValidationError
import config
from schemas.prd import PRD
from schemas.roadmap import RoadmapItem
from schemas.digest import StakeholderDigest

MAX_RETRIES = 2
# eng (longest body ~850 tokens + a compliant relay
# index of 15-20 technical claims) deterministically overran 2000. Budget
# cuts are detected and raised as a DISTINCT failure below — if this number
# is wrong again, it costs one call and one clear error, not three opaque ones.
MAX_TOKENS = 4000

TOOL_NAME = "submit_digest"

# Single StakeholderDigest — one object, valid tool input, no wrapper.
DIGEST_TOOL = {
    "name": TOOL_NAME,
    "description": "Submit the stakeholder digest for the target audience.",
    "input_schema": StakeholderDigest.model_json_schema(),
}

# Tone blocks: behavior-level, one injected per call. Contrast is written into
# the block, not achieved by showing the other blocks.
TONE_BLOCKS = {
    "eng": (
        "Your audience is the ENGINEERING TEAM.\n"
        "- Be precise and technical: name subsystems, behaviors, and\n"
        "  acceptance criteria directly.\n"
        "- Lead with what is being built and why it is hard or interesting.\n"
        "- Unlike an executive summary, do not translate work into business\n"
        "  outcomes — engineers want the shape of the work itself.\n"
        "- call_to_action: a concrete action an engineer takes (review a\n"
        "  section, flag a dependency, weigh in on a sequencing choice)."
    ),
    "exec": (
        "Your audience is EXECUTIVE LEADERSHIP.\n"
        "- Be outcome-focused: lead with what this work changes for users\n"
        "  and the product, not how it is implemented.\n"
        "- Frame scope in terms of priorities and sequencing (what ships\n"
        "  first and why), not technical detail.\n"
        "- Unlike an engineering brief, never name internal subsystems or\n"
        "  implementation mechanics unless the outcome is unintelligible\n"
        "  without them.\n"
        "- call_to_action: a decision or endorsement you are asking for\n"
        "  (approve a sequencing, greenlight a workstream)."
    ),
    "customer": (
        "Your audience is CUSTOMERS of the product.\n"
        "- Be benefit- and empathy-focused: name the frustration they have\n"
        "  felt, then what will improve for them.\n"
        "- No internal jargon: no subsystem names, no story points, no\n"
        "  quarters-as-planning-artifacts (say 'coming soon' or 'later this\n"
        "  year', not 'Q2').\n"
        "- Warm, plain language. Unlike internal summaries, you are writing\n"
        "  to someone who does not know or care how the team is organized.\n"
        "- call_to_action: an engagement step (try a feature when it lands,\n"
        "  share feedback, join a beta ONLY if the input mentions one)."
    ),
}

SYSTEM_PROMPT_TEMPLATE = """You are a product manager writing a stakeholder digest from a set of PRDs and a roadmap.

{audience_guidance}

Grounding discipline — this overrides everything, including tone:
- Never state a number, date, percentage, or dollar figure that does not
  appear verbatim in the input below. This applies to EVERY field, including
  call_to_action — do not invent deadlines, amounts, or launch dates.
- If the input has no number for something, describe it qualitatively.
  A digest with no numbers is a correct digest when the input has none.
- Do not invent reasons, causes, or rationales the input does not state.
  If the input gives a sequencing, scoring, or decision without a stated
  reason, report it without a reason — never manufacture a "why", even
  when your audience guidance asks you to explain priorities. The absence
  of a stated rationale is information; fabricating one destroys it.
- Every load-bearing factual claim in your prose must appear in key_claims,
  with grounded_in listing the theme(s) whose PRD or roadmap item supports it.
  A claim counts whether you restated it directly from the input or translated
  it into your own words — restating a fact from the input is still making
  that claim to your reader. Technical detail carried over from the input is
  not "connective tissue"; if a sentence tells the reader something checkable
  about what is broken, changing, or planned, it contains a claim.
- key_claims is an INDEX of claims already in your prose, not a quota to
  fill. An empty key_claims list is correct for a purely qualitative digest.
  Do not add claims to the prose to make key_claims look substantive.

Output fields:
- headline: one line, audience-appropriate hook.
- body: the narrative. 2-4 short paragraphs.
- call_to_action: one specific ask, per your audience guidance.
- key_claims: the index described above.
- audience: echo the target audience.
"""


def _peel(raw):
    """Deterministic encoding fix: if the tool input arrived as a JSON string,
    parse it. Not a repair — costs no retry."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw


def _project_prd(prd: PRD) -> str:
    """Digest-relevant view of one PRD: problem, users' stories, metrics
    (with targets — the legitimate numbers), risks. Unlike C4's scoring
    projection, success metrics are INCLUDED: their targets are exactly the
    real numbers a digest may cite, and withholding them would starve the
    model into either numberless prose or fabrication."""
    story_lines = [
        f"    - As {s.persona}, I want to {s.action}, so that {s.value}"
        for s in prd.user_stories
    ] or ["    (none)"]
    metric_lines = [
        f"    - {m.name}: {m.definition} (target: {m.target})"
        for m in prd.success_metrics
    ] or ["    (none)"]
    risk_lines = [
        f"    - [{r.severity}] {r.description}" for r in prd.risks
    ] or ["    (none)"]
    return (
        f"PRD theme: {prd.theme}\n"
        f"  problem_statement: {prd.problem_statement}\n"
        f"  user_stories:\n" + "\n".join(story_lines) + "\n"
        f"  success_metrics:\n" + "\n".join(metric_lines) + "\n"
        f"  risks:\n" + "\n".join(risk_lines)
    )


def _project_roadmap_item(item: RoadmapItem) -> str:
    """Digest-relevant view of one roadmap item: what, when, why-sized."""
    return (
        f"Roadmap item (theme: {item.prd_ref}): {item.title}\n"
        f"  scheduled: {item.quarter}\n"
        f"  effort: {item.effort.score} ({item.effort.rationale})\n"
        f"  impact: {item.impact.score}/5 ({item.impact.rationale})\n"
        f"  depends_on: {item.depends_on or 'nothing'}"
    )


def _build_input(prds: list[PRD], roadmap: list[RoadmapItem]) -> str:
    prd_block = "\n\n".join(_project_prd(p) for p in prds)
    rm_block = "\n\n".join(_project_roadmap_item(i) for i in roadmap)
    return f"=== PRDs ===\n\n{prd_block}\n\n=== ROADMAP ===\n\n{rm_block}"


def _validate_grounding(digest: StakeholderDigest, theme_set: set[str]) -> None:
    """Failure mode (a): membership check. Every grounded_in entry must name
    a theme present in the input. Validity is checked; quantity never is."""
    problems = []
    for i, claim in enumerate(digest.key_claims, start=1):
        bad = sorted(set(claim.grounded_in) - theme_set)
        if bad:
            problems.append(
                f"key_claims[{i}] ('{claim.text[:60]}...') cites unknown "
                f"theme(s) {bad}; valid themes are {sorted(theme_set)}."
            )
    if problems:
        raise ValueError("Invalid claim grounding:\n" + "\n".join(problems))


def summarize(
    prds: list[PRD], roadmap: list[RoadmapItem], audience: str
) -> StakeholderDigest:
    """One digest for one audience. Bounded repair loop covers both
    ValidationError (shape) and ValueError (dangling grounding refs) —
    both are reject-and-regenerate, structurally illegal outputs."""
    if audience not in TONE_BLOCKS:
        raise ValueError(
            f"Unknown audience '{audience}'; expected one of {sorted(TONE_BLOCKS)}."
        )
    theme_set = {p.theme for p in prds}
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = SYSTEM_PROMPT_TEMPLATE.format(audience_guidance=TONE_BLOCKS[audience])
    messages = [{"role": "user", "content": _build_input(prds, roadmap)}]
    last_error = "unknown"

    for attempt in range(1 + MAX_RETRIES):
        response = client.messages.create(
            model=config.AGENT_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[DIGEST_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=messages,
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise RuntimeError("Model returned no tool_use block despite forced tool_choice.")

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Digest for '{audience}' truncated at the token ceiling "
                f"(MAX_TOKENS={MAX_TOKENS}; {response.usage.output_tokens} generated). "
                f"Budget failure, not compliance — the repair loop cannot fix this "
                f"and retrying under the same budget is deterministic waste. "
                f"Raise MAX_TOKENS."
            )

        raw = _peel(tool_use.input)
        # Code stamps audience: the caller holds the provenance, the model's
        # echo is overwritten, not trusted.
        raw = {**raw, "audience": audience}

        try:
            digest = StakeholderDigest.model_validate(raw)
            _validate_grounding(digest, theme_set)
            return digest
        except (ValidationError, ValueError) as e:
            last_error = str(e)

        print(f"Digest validation failed for '{audience}' on attempt {attempt + 1}; retrying.")
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
                            f"Your submitted digest failed validation:\n\n{last_error}\n\n"
                            f"Resubmit the full digest. Fix only what the error names; "
                            f"change nothing else."
                        ),
                    }
                ],
            },
        ]

    raise RuntimeError(
        f"Digest for '{audience}' failed after {1 + MAX_RETRIES} attempts. "
        f"Last error:\n{last_error}"
    )


# ==========================================================================
# Slack composition (C7): exec digest -> channel post
# ==========================================================================
#
# Free-prose output, deliberately NOT tool-forced: there is no structure to
# enforce, and a schema here would be ceremony. The model's job is editorial
# condensation — the one post-gate composition in the pipeline where judgment
# genuinely remains (no human ratified the digest's wording; it is already
# model-authored prose).

SLACK_COMPOSE_SYSTEM = (
    "You condense an executive stakeholder digest into a short Slack channel post.\n"
    "Rules:\n"
    "- Use only facts present in the digest. Do not add numbers, dates, names, "
    "or commitments that are not in it.\n"
    "- A few sentences at most: what happened, why it matters, then the ask.\n"
    "- Plain text only — no markdown headers, no bullet lists, no preamble like "
    "'Here is the post'. Output the post text and nothing else."
)

SLACK_COMPOSE_MAX_TOKENS = 600


def compose_slack_post(digest: StakeholderDigest) -> str:
    """Condense the exec digest's reader-facing prose into a Slack post.

    key_claims is deliberately excluded from the input: it is the judge-facing
    sidecar and carries full jargon regardless of audience tone — feeding it
    to the composer invites jargon leakage into a channel post.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.AGENT_MODEL,
        max_tokens=SLACK_COMPOSE_MAX_TOKENS,
        system=SLACK_COMPOSE_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"HEADLINE: {digest.headline}\n\n"
                f"BODY:\n{digest.body}\n\n"
                f"CALL TO ACTION: {digest.call_to_action}"
            ),
        }],
    )
    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Slack post truncated at the token ceiling "
            f"(SLACK_COMPOSE_MAX_TOKENS={SLACK_COMPOSE_MAX_TOKENS}; "
            f"{response.usage.output_tokens} generated). Budget failure — raise the ceiling."
        )
    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        raise RuntimeError("Model returned no text block for the Slack post.")
    return text_block.text.strip()
