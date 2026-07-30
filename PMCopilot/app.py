"""C8 — Streamlit dashboard: staged streaming, caller-side gate, and views.

Run from project root:  uv run streamlit run app.py

Four tabs. Run streams the graph and hosts the approval gate; PRDs, Roadmap,
and Digests read a session-scoped ledger of updates-chunk payloads.

TWO SEPARATE GUARANTEES, deliberately not the same one:

- Events: the live-painted transcript and render_events()'s replay must agree.
  Stages paint as debug events arrive, then the stream ends with st.rerun() so
  the replayed screen immediately replaces the live one — a divergence surfaces
  the instant a run finishes rather than later.

- Views: the ledger is a TRANSCRIPT, not a state mirror, and legitimately holds
  more than the checkpoint. `prds` is last-write-wins, so a revise pass replaces
  the draft in state while the ledger keeps both. Views are EXPECTED to disagree
  with graph.get_state(); that disagreement is the reason for capturing at all.

The ledger stores destructured records only — node / channel / value / seq / run.
`is_current` and draft-vs-revision labelling depend on the whole sequence, which
does not exist when a record arrives, so both are computed at render time.

The cross-topic roadmap is an ARTIFACT, not a rendering: plan() is a model call,
so re-deriving it yields different scores. It is computed on an explicit press,
stored with the PRD-record seqs it was planned over, and flagged stale when that
set changes.

Known seam: session_state does not survive a browser refresh, so a reload loses
the ledger while the checkpoint survives. The gate falls back to interrupt()'s
five-field projection in that case.
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
from agents.planner import plan, QUARTERS

DB = "pmcopilot_demo.sqlite"
CORPUS = "langchain-ai/langchain — 200 issues"
SKIP_STAGES = {"supervisor", "approval_gate"}   # routing locus, writes nothing, renders as noise
SEVERITY = {"high": "red", "medium": "orange", "low": "gray"}

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


def capture(chunk: dict) -> None:
    """Append one ledger record per channel written by one node execution.

    Destructuring only. Every field is read off the chunk or off state that
    already exists here; nothing decides what a record MEANS. `is_current` and
    draft/revision labelling are render-time concerns because both depend on
    the whole sequence, which does not exist yet when a record arrives.

    The error path needs no special case: a node that failed returns
    {"error_messages": [...], "current_step": "error"}, which yields two
    records under the same rule. Views filtering on channel simply never see
    them.
    """
    ledger = st.session_state.ledger
    for node, updates in chunk.items():
        if not isinstance(updates, dict):   # __interrupt__ carries a tuple
            continue
        for channel, value in updates.items():
            ledger.append({
                "seq": len(ledger),
                "run": st.session_state.thread_id,
                "node": node,
                "channel": channel,
                "value": value,
            })


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
            capture(chunk)
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


def _prd_records(ledger: list[dict]) -> list[dict]:
    """Ledger -> PRD cards, oldest first, with render-time labels.

    `revision` and `is_current` are computed HERE and never stamped at capture.
    Both depend on how many prds records a run ends up producing, which is
    unknowable while that run is still streaming — the same reason `quarter`
    can't be a per-item model field.
    """
    out, seen = [], {}
    for rec in ledger:
        if rec["channel"] != "prds":
            continue
        n = seen.get(rec["run"], 0)
        seen[rec["run"]] = n + 1
        out.append({**rec, "revision": n})

    last = {r["run"]: r["seq"] for r in out}      # dict comp keeps the last write
    for r in out:
        r["is_current"] = r["seq"] == last[r["run"]]
    return out


def _current_prd(ledger: list[dict], run: str):
    """The PRD a run is currently working from — its last prds record.

    Reads the UI's transcript rather than interrupt()'s payload. Both resolve to
    state["prds"][-1], so it's the same object; the difference is that the
    interrupt carries a five-field projection while the ledger holds all eight.
    """
    for rec in reversed(ledger):
        if rec["channel"] == "prds" and rec["run"] == run:
            return rec["value"][-1]
    return None


def _render_prd_card(prd) -> None:
    st.markdown("**Problem**")
    st.write(prd.problem_statement)
    st.markdown("**Target user**")
    st.write(prd.target_user)

    st.markdown(f"**User stories** ({len(prd.user_stories)})")
    for us in prd.user_stories:
        st.markdown(f"- As **{us.persona}**, I want to {us.action}, so that {us.value}")

    st.markdown(f"**Acceptance criteria** ({len(prd.acceptance_criteria)})")
    for ac in prd.acceptance_criteria:
        st.markdown(f"- *Given* {ac.given} · *when* {ac.when} · *then* {ac.then}")

    if prd.success_metrics:
        st.markdown("**Success metrics**")
        st.table([
            {"Metric": m.name, "Target": m.target, "Definition": m.definition}
            for m in prd.success_metrics
        ])

    if prd.out_of_scope:
        st.markdown("**Out of scope**")
        for item in prd.out_of_scope:
            st.markdown(f"- {item}")

    if prd.risks:
        st.markdown("**Risks**")
        for r in prd.risks:
            st.markdown(f"- :{SEVERITY[r.severity]}[**{r.severity.upper()}**] — {r.description}")


def render_prd_repository(ledger: list[dict]) -> None:
    """Accumulates across runs — a repository, not a board.

    One card per PRD *record*, so a revise run yields draft and revision side
    by side. This is the transcript ledger paying for itself: the checkpoint
    holds only the survivor.
    """
    st.subheader("PRD repository")
    records = _prd_records(ledger)
    if not records:
        st.caption("No PRDs yet — the drafter runs after discovery.")
        return
    revised = {r["run"] for r in records if r["revision"] > 0}
    for rec in records:
        for prd in rec["value"]:
            label = "draft" if rec["revision"] == 0 else f"revision {rec['revision']}"
            # `· current` earns its place only where a run has more than one
            # version; every run has a current PRD, so on a single-version run
            # the marker distinguishes nothing.
            mark = " · current" if rec["is_current"] and rec["run"] in revised else ""
            with st.expander(f"{prd.theme} — {label}{mark}", expanded=False):
                _render_prd_card(prd)


def _current_records(ledger: list[dict]) -> list[dict]:
    """The current PRD record per run — never the superseded draft.

    Returns records rather than bare PRDs so callers can use `seq` as a version
    stamp. Theme can't serve: it's code-stamped from the topic, so a revision
    carries the same theme as the draft it replaced.
    """
    return [rec for rec in _prd_records(ledger) if rec["is_current"]]


def render_roadmap(ledger: list[dict]) -> None:
    """Four columns because _assign_quarters emits exactly Q1-Q4.

    The roadmap is an ARTIFACT, not a rendering: plan() is a model call, so two
    invocations over the same PRD set yield different scores and possibly
    different quarters. It is therefore computed on an explicit press and stored
    with the PRD set it was planned over — a roadmap that predates a newly added
    PRD is detectably stale rather than silently wrong.
    """
    st.subheader("Roadmap")
    records = _current_records(ledger)
    prds = [rec["value"][-1] for rec in records]
    themes = [p.theme for p in prds]
    stamp = [rec["seq"] for rec in records]

    left, right = st.columns([1, 4])
    with left:
        go = st.button("Re-plan", type="primary", disabled=not prds)
    with right:
        st.caption(f"{len(prds)} PRD(s) in repository: {', '.join(themes) or '—'}")

    if go:
        with st.spinner(f"Scoring and sequencing {len(prds)} PRDs..."):
            try:
                ss.roadmap_artifact = {
                    "items": plan(prds),
                    "planned_over": themes,
                    "stamp": stamp,
                    "at": datetime.now(timezone.utc).strftime("%H:%M:%SZ"),
                }
            except Exception as exc:
                # _assign_quarters raises past four quarters. Caught rather than
                # propagated: an uncaught raise in a tab body kills the page,
                # including the Run tab mid-gate.
                st.error(f"Planning failed: {type(exc).__name__}: {exc}")

    artifact = ss.roadmap_artifact
    if artifact is None:
        st.info("No roadmap yet — add PRDs on different topics, then press Re-plan.")
        return

    if artifact["stamp"] != stamp:
        st.warning(
            f"Stale — planned over {len(artifact['planned_over'])} PRD(s) "
            f"({', '.join(artifact['planned_over'])}) at {artifact['at']}. "
            "The repository has changed since — a PRD was added or revised."
        )
    else:
        st.caption(f"Planned {artifact['at']} over {len(themes)} PRD(s).")

    by_q = {q: [] for q in QUARTERS}
    for item in artifact["items"]:
        by_q[item.quarter].append(item)

    for col, q in zip(st.columns(len(QUARTERS)), QUARTERS):
        with col:
            load = sum(i.effort.score for i in by_q[q])
            st.markdown(f"**{q}**")
            st.caption(f"{len(by_q[q])} item(s) · {load} pts" if by_q[q] else "—")
            for item in by_q[q]:
                with st.container(border=True):
                    st.markdown(f"**{item.title}**")
                    st.caption(f"effort {item.effort.score} · impact {item.impact.score}")
                    if item.depends_on:
                        st.caption(f"depends on: {', '.join(item.depends_on)}")
                    with st.popover("Rationale", use_container_width=True):
                        st.markdown(f"**{item.title}**")
                        st.markdown(f"*Effort {item.effort.score}* — {item.effort.rationale}")
                        st.markdown(f"*Impact {item.impact.score}* — {item.impact.rationale}")


# ---------------------------------------------------------------- state
ss = st.session_state
ss.setdefault("phase", "idle")          # idle -> streaming -> awaiting_verdict / done
ss.setdefault("events", [])
ss.setdefault("thread_id", None)
ss.setdefault("topic", None)
ss.setdefault("proposal", None)
ss.setdefault("ledger", [])
ss.setdefault("roadmap_artifact", None)

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
    tab_run, tab_prds, tab_roadmap, tab_digests = st.tabs(
        ["Run", "PRDs", "Roadmap", "Digests"]
    )

    # View tabs render BEFORE the run loop deliberately. run_stream blocks for
    # ~1min and ends in st.rerun(), which halts the script — anything below it
    # never executes. Painting the read-only views first means a mid-stream tab
    # switch shows prior content instead of a blank panel.
    with tab_prds:
        render_prd_repository(ss.ledger)

    with tab_roadmap:
        render_roadmap(ss.ledger)

    with tab_digests:
        st.info("Digest viewer — next build.")

    with tab_run:
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
            prd = _current_prd(ss.ledger, ss.thread_id)
            with st.container(height=480, border=True):
                if prd is not None:
                    _render_prd_card(prd)
                else:
                    # Cold-load seam: unreachable today (awaiting_verdict is only
                    # entered by streaming in this session), but this is where the
                    # parked refresh-recovery item lands. The graph's own payload
                    # is the five-field projection.
                    st.json(
                        graph.get_state(cfg).tasks[0].interrupts[0].value["review"],
                        expanded=False,
                    )

        if ss.phase == "awaiting_verdict":
            verdict = st.text_area("Your verdict", placeholder="approve, or say what to change")
            if st.button("Submit", type="primary", disabled=not verdict):
                with st.spinner("Interpreting..."):
                    proposal = interpret_verdict(verdict)
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

            if st.button("New run"):
                ss.phase = "idle"
                ss.thread_id = None
                ss.topic = None
                ss.events = []
                st.rerun()  # ledger deliberately NOT cleared
