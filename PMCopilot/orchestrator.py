"""C6 — LangGraph orchestrator: state definition."""
import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict
from schemas.discovery import DiscoveryFinding   # adjust if your import path differs
from schemas.prd import PRD
from agents.discovery import research
from agents.prd_drafter import draft_prd
from schemas.roadmap import RoadmapItem
from schemas.digest import StakeholderDigest
from agents.planner import plan
from agents.summarizer import summarize, TONE_BLOCKS
from langgraph.graph import StateGraph, START, END
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import interrupt
from mcp_client import call_tool


class PMCopilotState(TypedDict):
    # inputs
    topic: str

    # artifacts (typed — objects flow through the graph)
    findings: Optional[DiscoveryFinding]
    prds: list[PRD]
    roadmap: Optional[list[RoadmapItem]]  # C4 artifact; last-write-wins (redo replaces, same class as prds)
    digests: Annotated[list[StakeholderDigest], operator.add]  # C5 artifacts + progress ledger; append-only by channel

    # control
    current_step: str
    error_messages: Annotated[list[str], operator.add]
    revision_feedback: Optional[str]  # gate → drafter channel; set on revise, cleared on approve
    jira_issue_id: Optional[int]  # C7 artifact ref; written by jira_node post-approval


# Stamp vocabulary — the router (Step 3) keys off exactly these values.
STEP_START = "start"
STEP_DISCOVERY_DONE = "discovery_done"
STEP_DRAFTING_DONE = "drafting_done"
STEP_ERROR = "error"
STEP_PLANNING_DONE = "planning_done"
STEP_SUMMARIZING_DONE = "summarizing_done"
STEP_APPROVED = "approved"
STEP_REVISION_REQUESTED = "revision_requested"
STEP_JIRA_FILED = "jira_filed"


def discovery_node(state: PMCopilotState) -> dict:
    """C2 wrapper: topic -> DiscoveryFinding."""
    try:
        finding = research(state["topic"])
        return {"findings": finding, "current_step": STEP_DISCOVERY_DONE}
    except Exception as exc:
        return {
            "error_messages": [f"discovery_node: {type(exc).__name__}: {exc}"],
            "current_step": STEP_ERROR,
        }


def prd_node(state: PMCopilotState) -> dict:
    """C3 wrapper: DiscoveryFinding -> [PRD]."""
    try:
        prd = draft_prd(state["findings"], feedback=state.get("revision_feedback"))
        return {"prds": [prd], "current_step": STEP_DRAFTING_DONE}
    except Exception as exc:
        return {
            "error_messages": [f"prd_node: {type(exc).__name__}: {exc}"],
            "current_step": STEP_ERROR,
        }


def _remaining_audiences(state: PMCopilotState) -> list[str]:
    """Progress derived from the digests ledger itself — no separate bookkeeping field."""
    done = {d.audience for d in state["digests"]}
    return sorted(set(TONE_BLOCKS) - done)


def planner_node(state: PMCopilotState) -> dict:
    """C4 wrapper: [PRD] -> [RoadmapItem]."""
    try:
        roadmap = plan(state["prds"])
        return {"roadmap": roadmap, "current_step": STEP_PLANNING_DONE}
    except Exception as exc:
        return {
            "error_messages": [f"planner_node: {type(exc).__name__}: {exc}"],
            "current_step": STEP_ERROR,
        }


def summarizer_node(state: PMCopilotState) -> dict:
    """C5 wrapper: one audience per superstep; each digest is its own checkpoint.

    The router only sends control here while audiences remain, so [0] is
    safe by invariant — a violated invariant fails loud (IndexError).
    """
    audience = _remaining_audiences(state)[0]
    try:
        digest = summarize(state["prds"], state["roadmap"], audience)
        return {"digests": [digest], "current_step": STEP_SUMMARIZING_DONE}
    except Exception as exc:
        return {
            "error_messages": [f"summarizer_node[{audience}]: {type(exc).__name__}: {exc}"],
            "current_step": STEP_ERROR,
        }


def _prd_review_payload(prd: PRD) -> dict:
    """Serializable projection of the PRD for human review at the gate."""
    return {
        "theme": prd.theme,
        "problem_statement": prd.problem_statement,
        "target_user": prd.target_user,
        "user_stories": [us.model_dump() for us in prd.user_stories],
        "acceptance_criteria": [ac.model_dump() for ac in prd.acceptance_criteria],
    }


def approval_node(state: PMCopilotState) -> dict:
    """Human-in-loop gate after C3.

    Pauses with the drafted PRD; the resume value is an already-confirmed
    structured decision — interpret-then-confirm is caller protocol
    (demo script today, Streamlit in C8), not graph topology.
    """
    decision = interrupt({
        "review": _prd_review_payload(state["prds"][-1]),
        "resume_contract": "{'action': 'approve'|'revise', 'feedback': str|None}",
    })
    if decision["action"] == "approve":
        return {"revision_feedback": None, "current_step": STEP_APPROVED}
    return {
        "revision_feedback": decision.get("feedback"),
        "current_step": STEP_REVISION_REQUESTED,
    }


def jira_node(state: PMCopilotState) -> dict:
    """C7 wrapper: file the approved PRD as a tracking issue via MCP.

    Deterministic by design — the human gate already ratified the PRD's wording,
    so issue fields are a code mapping from the approved artifact, not a model
    composition. The MCP protocol boundary is real (stdio subprocess); only the
    argument authorship is code-side.
    """
    prd = state["prds"][-1]
    try:
        issue = call_tool("create_issue", {
            "data": {
                "title": f"[PRD] {prd.theme}",
                "body": prd.problem_statement,
            }
        })
        return {"jira_issue_id": issue["id"], "current_step": STEP_JIRA_FILED}
    except Exception as exc:
        return {
            "error_messages": [f"jira_node: {type(exc).__name__}: {exc}"],
            "current_step": STEP_ERROR,
        }


def supervisor_node(state: PMCopilotState) -> dict:
    """Deterministic supervisor: holds no logic, writes nothing.

    Routing lives in route_from_supervisor; this node exists so the graph
    has an explicit control locus to hang gates on in Day 25.
    """
    return {}


ROUTE_TABLE = {
    STEP_START: "discovery",
    STEP_DISCOVERY_DONE: "drafter",
    STEP_DRAFTING_DONE: "approval_gate",
    STEP_APPROVED: "jira",
    STEP_REVISION_REQUESTED: "drafter",
    STEP_JIRA_FILED: "planner",
    STEP_PLANNING_DONE: "summarizer",
    STEP_ERROR: END,
}


def route_from_supervisor(state: PMCopilotState) -> str:
    step = state.get("current_step", STEP_START)
    if step == STEP_SUMMARIZING_DONE:
        return "summarizer" if _remaining_audiences(state) else END
    return ROUTE_TABLE[step]


def build_graph(checkpointer=None, interrupt_before=None):
    g = StateGraph(PMCopilotState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("discovery", discovery_node)
    g.add_node("drafter", prd_node)
    g.add_node("planner", planner_node)
    g.add_node("summarizer", summarizer_node)
    g.add_node("approval_gate", approval_node)
    g.add_node("jira", jira_node)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_from_supervisor, ["discovery", "drafter", "approval_gate", "planner", "summarizer", "jira", END],)
    g.add_edge("discovery", "supervisor")
    g.add_edge("drafter", "supervisor")
    g.add_edge("planner", "supervisor")
    g.add_edge("summarizer", "supervisor")
    g.add_edge("approval_gate", "supervisor")
    g.add_edge("jira", "supervisor")

    return g.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


# Explicit registration of checkpoint-crossing artifact types.
# Guards the typed-state lock against langgraph's announced default-block.
CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("schemas.discovery", "DiscoveryFinding"),
        ("schemas.prd", "PRD"),
        ("schemas.roadmap", "RoadmapItem"),
        ("schemas.digest", "StakeholderDigest"),
    ]
)


def make_saver(db_path: str) -> SqliteSaver:
    """Standard saver construction — callers still decide *whether* to persist."""
    return SqliteSaver(
        sqlite3.connect(db_path, check_same_thread=False),
        serde=CHECKPOINT_SERDE,
    )
