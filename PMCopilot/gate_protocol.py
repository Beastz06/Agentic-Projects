"""Caller-side protocol for the approval gate: free text -> structured proposal.

The graph pauses at approval_gate and resumes with a confirmed decision.
Turning human free text into that decision is conversation handling, owned
by whoever owns the conversation medium (CLI script today, Streamlit in C8).
"""
import anthropic
import config

PROPOSAL_TOOL = {
    "name": "routing_proposal",
    "description": "Structured interpretation of the reviewer's free-text verdict on a PRD.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["approve", "revise"],
                "description": "approve = PRD proceeds to roadmap planning; revise = PRD returns to the drafter.",
            },
            "feedback": {
                "type": ["string", "null"],
                "description": (
                    "Only for revise: the reviewer's revision instruction, restated "
                    "faithfully and concisely from their words. Do not add requirements "
                    "the reviewer did not state. null for approve."
                ),
            },
        },
        "required": ["action", "feedback"],
    },
}

SYSTEM = (
    "You interpret a human reviewer's free-text verdict on a draft PRD into a "
    "structured routing proposal. The human will confirm your interpretation "
    "before it takes effect — when their intent is ambiguous, prefer 'revise' "
    "with their words as feedback over guessing 'approve'."
)


def interpret_verdict(free_text: str) -> dict:
    """One LLM call: reviewer free text -> {'action': ..., 'feedback': ...}.

    Raises RuntimeError on a malformed response; the caller re-asks the human.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.AGENT_MODEL,
        max_tokens=300,
        system=SYSTEM,
        tools=[PROPOSAL_TOOL],
        tool_choice={"type": "tool", "name": "routing_proposal"},
        messages=[{"role": "user", "content": f"Reviewer's verdict:\n{free_text}"}],
    )
    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None or tool_use.input.get("action") not in ("approve", "revise"):
        raise RuntimeError(f"Interpreter returned no valid proposal: {response.content}")
    return {"action": tool_use.input["action"], "feedback": tool_use.input.get("feedback")}
