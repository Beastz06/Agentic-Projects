"""C8 — Streamlit dashboard (Part 1): boot, topic input, staged streaming.

Run from project root:  uv run streamlit run app.py

Two display paths must agree. During a stream, stages paint live as debug
events arrive. On every other rerun, render_events() replays the transcript
from session_state. The stream deliberately ends with st.rerun() so the
replayed screen immediately replaces the live-painted one — if the two ever
disagree, it shows the instant a run finishes rather than on Day 30.
"""
import logging
from datetime import datetime, timezone
import streamlit as st
import config
import telemetry
from agents.prd_drafter import MAX_RETRIES
from orchestrator import build_graph, make_saver
from gate_protocol import interpret_verdict
from langgraph.types import Command

DB = "pmcopilot_demo.sqlite"
CORPUS = "langchain-ai/langchain — 200 issues"
SKIP_STAGES = {"supervisor", "approval_gate"}   # routing locus, writes nothing, renders as noise

st.set_page_config(page_title="PMCopilot", layout="wide")


@st.cache_resource
def get_graph():
    """One graph, one SqliteSaver connection, shared across reruns.

    cache_resource is cross-session, which is correct here: the graph holds no
    per-run state — that lives in the checkpointer, keyed by thread_id. The
    connection is already check_same_thread=False.
    """
    return build_graph(checkpointer=make_saver(DB))


class Sink:
    """Mutable container holder, re-pointed by the stream loop as stages advance.

    telemetry.py takes a callable, not a Streamlit object, so it stays free of
    any streamlit import and C9 can construct the same handler with sink=None.
    """

    def __init__(self):
        self.container = None

    def __call__(self, event: dict) -> None:
        if self.container is not None:
            self.container.write(_format(event))


def _format(event: dict) -> str:
    if event.get("pmc_event") == telemetry.EVENT_REPAIR_FIRE:
        return f"⚠️ {event.get('message', '')}"
    return event.get("message", "")


def attach_handler(sink=None) -> None:
    """Rebuild the handler every script run rather than caching it.

    Streamlit re-executes top to bottom, so a cached handler would hold a stale
    container reference from the previous run. Rebuilding is cheaper than
    invalidating. Events live in session_state, so the transcript survives even
    though the handler does not.
    """
    logger = logging.getLogger(telemetry.ROOT)
    logger.setLevel(logging.DEBUG)
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    logger.addHandler(
        telemetry.TelemetryHandler(events=st.session_state.events, sink=sink)
    )


def render_events(events: list[dict]) -> None:
    """Replay a transcript. Walks stage markers to reconstruct nesting —
    grouping by logger name would collapse a revise pass into the first draft."""
    current = None
    for event in events:
        kind = event.get("pmc_event")
        if kind == telemetry.EVENT_STAGE_START:
            current = st.status(event["pmc_stage"], state="complete", expanded=False)
        elif kind == telemetry.EVENT_STAGE_END:
            current = None
        elif current is not None:
            current.write(_format(event))
        else:
            st.write(_format(event))


def run_stream(graph, cfg, payload, sink) -> bool:
    """Drive the graph, painting stages live. Returns True if it hit the gate.

    Stage boundaries come from debug 'task' / 'task_result' events, which
    bracket the node's execution — a node's own updates chunk arrives only
    after it has finished, too late to open a container that mid-node retries
    can paint into.
    """
    events = st.session_state.events
    interrupted = False

    for mode, chunk in graph.stream(payload, cfg, stream_mode=["updates", "debug"]):
        if mode == "updates":
            if "__interrupt__" in chunk:
                interrupted = True
            continue

        ctype = chunk.get("type")
        if ctype not in ("task", "task_result"):
            continue
        name = chunk["payload"]["name"]
        if name in SKIP_STAGES:
            continue

        if ctype == "task":
            telemetry.stage_marker(events, name)
            sink.container = st.status(name, expanded=True)
        else:
            telemetry.stage_marker(events, name, end=True)
            if sink.container is not None:
                sink.container.update(state="complete", expanded=False)
            sink.container = None

    return interrupted


# ---------------------------------------------------------------- state
ss = st.session_state
ss.setdefault("phase", "idle")          # idle -> streaming -> awaiting_verdict / done
ss.setdefault("events", [])
ss.setdefault("thread_id", None)
ss.setdefault("topic", None)
ss.setdefault("proposal", None)

graph = get_graph()
cfg = {"configurable": {"thread_id": ss.thread_id}} if ss.thread_id else None

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.subheader("Configuration")
    st.text_input("Corpus", CORPUS, disabled=True)
    st.text_input("Model", config.AGENT_MODEL, disabled=True)
    st.text_input("Repair budget", f"{MAX_RETRIES} retries", disabled=True)
    st.caption(
        "Read-only. The corpus is a single prebuilt index; switching models "
        "would invalidate the C9 failure-mode baseline."
    )
    if ss.thread_id:
        st.divider()
        st.caption(f"thread: `{ss.thread_id}`")

# ---------------------------------------------------------------- main
st.title("PMCopilot")

if ss.phase == "idle":
    topic = st.text_input("Topic", placeholder="e.g. streaming behavior and chunk handling")
    if st.button("Run", type="primary", disabled=not topic):
        ss.topic = topic
        ss.thread_id = f"ui-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        ss.events = []
        ss.phase = "streaming"
        st.rerun()

else:
    st.caption(f"Topic: {ss.topic}")

    # Snapshot before streaming: replay what already happened, then let the
    # loop append and paint new events. No double-painting, one code path.
    render_events(list(ss.events))

    if ss.phase in ("streaming", "resuming"):
        sink = Sink()
        attach_handler(sink)
        payload = (
            {"topic": ss.topic} if ss.phase == "streaming"
            else Command(resume=ss.proposal)
        )
        hit_gate = run_stream(graph, cfg, payload, sink)
        ss.proposal = None
        ss.phase = "awaiting_verdict" if hit_gate else "done"
        st.rerun()

    attach_handler()  # collect-only while idle

    if ss.phase in ("awaiting_verdict", "awaiting_confirm"):
        st.subheader("PRD for review")
        review = graph.get_state(cfg).tasks[0].interrupts[0].value["review"]
        st.json(review, expanded=False)

    if ss.phase == "awaiting_verdict":
        verdict = st.text_area("Your verdict", placeholder="approve, or say what to change")
        if st.button("Submit", type="primary", disabled=not verdict):
            with st.spinner("Interpreting..."):
                proposal = interpret_verdict(verdict)
            # Defensive: run_gate_demo's `while proposal is None` implies
            # interpret_verdict may return None. I haven't read gate_protocol.py,
            # so this handles it rather than assuming. Costs three lines.
            if proposal is None:
                st.error("Couldn't interpret that — try rephrasing.")
            else:
                ss.proposal = proposal
                ss.phase = "awaiting_confirm"
                st.rerun()

    if ss.phase == "awaiting_confirm":
        st.write("Interpreted as:")
        st.json(ss.proposal)
        left, right = st.columns(2)
        if left.button("Confirm", type="primary"):
            ss.phase = "resuming"
            st.rerun()
        if right.button("Re-enter"):
            ss.proposal = None
            ss.phase = "awaiting_verdict"
            st.rerun()

    if ss.phase == "done":
        st.success("Run complete.")
        final = graph.get_state(cfg).values
        st.json({
            "jira_issue_id": final.get("jira_issue_id"),
            "notion_page_id": final.get("notion_page_id"),
            "slack_message_ts": final.get("slack_message_ts"),
            "roadmap_items": len(final.get("roadmap") or []),
            "digests": [d.audience for d in final.get("digests", [])],
            "errors": final.get("error_messages") or "none",
        })
