"""C6 — LangGraph orchestrator: state definition."""
import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict
from schemas.discovery import DiscoveryFinding   # adjust if your import path differs
from schemas.prd import PRD
from agents.discovery import research
from agents.prd_drafter import draft_prd
from langgraph.graph import StateGraph, START, END


class PMCopilotState(TypedDict):
    # inputs
    topic: str

    # artifacts (typed — objects flow through the graph)
    findings: Optional[DiscoveryFinding]
    prds: list[PRD]
    roadmap: Optional[dict]          # placeholder until C4 is wired (Part 2)
    digests: list[dict]              # placeholder until C5 is wired (Part 2)

    # control
    current_step: str
    error_messages: Annotated[list[str], operator.add]


# Stamp vocabulary — the router (Step 3) keys off exactly these values.
STEP_START = "start"
STEP_DISCOVERY_DONE = "discovery_done"
STEP_DRAFTING_DONE = "drafting_done"
STEP_ERROR = "error"


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
        prd = draft_prd(state["findings"])
        return {"prds": [prd], "current_step": STEP_DRAFTING_DONE}
    except Exception as exc:
        return {
            "error_messages": [f"prd_node: {type(exc).__name__}: {exc}"],
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
    STEP_DRAFTING_DONE: END,
    STEP_ERROR: END,
}


def route_from_supervisor(state: PMCopilotState) -> str:
    step = state.get("current_step", STEP_START)
    return ROUTE_TABLE[step]


def build_graph():
    g = StateGraph(PMCopilotState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("discovery", discovery_node)
    g.add_node("drafter", prd_node)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_from_supervisor, ["discovery", "drafter", END],)
    g.add_edge("discovery", "supervisor")
    g.add_edge("drafter", "supervisor")

    return g.compile()
