"""Telemetry channel for agent-internal process events.

A repair fire is telemetry, not state: it describes how a run reached its
outcome, not what the outcome was. The outcome — exhaustion — already has a
state channel (`error_messages`) and a routing edge (STEP_ERROR -> END).
This module carries the process side, which nothing routes on.

Library-style by design: this module emits and never configures. No handler,
no level, no basicConfig. Entry points decide where records go — the Streamlit
app renders them, run_gate_demo.py lets them fall to stderr, the C9 harness
collects them. Three consumers, one emission.

Namespace is `pmcopilot.*` rather than `__name__` so that a single handler on
`pmcopilot` captures the whole tree and captures nothing else: langchain,
httpx, chromadb, and mcp log on their own trees and never reach it.
"""
import logging

ROOT = "pmcopilot"

# Component identity is carried by record.name. No field duplicates it.
discovery_log = logging.getLogger(f"{ROOT}.discovery")
drafter_log = logging.getLogger(f"{ROOT}.drafter")
planner_log = logging.getLogger(f"{ROOT}.planner")
summarizer_log = logging.getLogger(f"{ROOT}.summarizer")
judge_log = logging.getLogger(f"{ROOT}.judge")

EVENT_REPAIR_FIRE = "repair_fire"
EVENT_STAGE_START = "stage_start"
EVENT_STAGE_END = "stage_end"
EVENT_MODEL_CALL = "model_call"

# Coined origins — for checks that reject without raising, so no exception
# type exists to name. Everything else passes type(e).__name__ through.
DEFECT_PROSE_ID_LEAK = "ProseIdLeak"
DETAIL_LIMIT = 200


def repair_fire(
    logger: logging.Logger,
    *,
    attempt: int,
    defect_origin: str,
    detail: str,
    site: str | None = None,
    subject: str | None = None,
) -> None:
    """Emit one repair-loop retry.

    attempt        1-indexed number of the attempt that FAILED.
    defect_origin  which check rejected the output. type(e).__name__ where an
                   exception was caught; a coined DEFECT_* constant where the
                   check rejects without raising. Names the origin, not the
                   defect — separating wrapper-nesting from Risk-collapse is
                   still C9's job.
    detail         prose description of the defect. Deliberately NOT a field:
                   separating wrapper-nesting from Risk-collapse is
                   classification, which is C9's job over a stable key, not a
                   taxonomy guessed today. Truncated to DETAIL_LIMIT here;
                   the budget is C9's to set, in one place.
    site           sub-loop within a component, where one exists
                   ("scoring" / "dependency" on the planner). None elsewhere.
    subject        what the loop was working on ("eng" / "exec" / "customer").
                   None where the component has no per-subject dimension.

    All extra keys carry a `pmc_` prefix. Not for collision safety — none of
    the five names here collide with a reserved LogRecord attribute. The
    prefix lets consumers extract telemetry in bulk without an allowlist:
    the Streamlit handler and the C9 collector both do
    {k: v for k, v in record.__dict__.items() if k.startswith("pmc_")},
    which stays correct when a sixth field is added. Collision IS a real
    mechanism (extra={"module": ...} raises KeyError) — it just isn't what
    drives the choice here.
    """
    detail = str(detail)[:DETAIL_LIMIT]
    qualifier = f" [{site or subject}]" if (site or subject) else ""
    logger.warning(
        "repair fire%s: attempt %d failed (%s); retrying. %s",
        qualifier,
        attempt,
        defect_origin,
        detail,
        extra={
            "pmc_event": EVENT_REPAIR_FIRE,
            "pmc_attempt": attempt,
            "pmc_defect_origin": defect_origin,
            "pmc_site": site,
            "pmc_subject": subject,
        },
    )


def model_call(
    logger: logging.Logger,
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    attempt: int = 1,
    site: str | None = None,
    subject: str | None = None,
) -> None:
    """Emit one completed model call.

    Tokens, not dollars. A token count is a fact about what happened; a price
    is a fact about the world at report time. Costing here would freeze a
    price into an append-only record and leave no legal way to correct it.
    The pricing table lives with the report.

    model          as reported by the response, not a local constant, so a
                   record survives the constant being changed or an alias
                   resolving to something else.
    latency_ms     wall clock around the create() call, including the network.
                   Not server-side generation time; nothing exposes that.
    attempt        1-indexed, matching repair_fire. A retry resends the full
                   prior turn, so attempt 2 carries roughly double the input
                   of attempt 1 -- the surcharge is only visible if each
                   attempt emits its own record.
    site           sub-loop within a component, where one exists ("scoring" /
                   "dependency" on the planner). None elsewhere.
    subject        what the call was working on -- a digest tone, a judge
                   dimension. None where the component has no such dimension.

    Emitted at INFO: a completed call is not a warning. This is the first
    non-warning event on this tree, which makes the module's emit-never-
    configure rule load-bearing -- see the note on consumers above.
    """
    logger.info(
        "model call: %s in=%d out=%d %dms",
        model,
        input_tokens,
        output_tokens,
        latency_ms,
        extra={
            "pmc_event": EVENT_MODEL_CALL,
            "pmc_model": model,
            "pmc_input_tokens": input_tokens,
            "pmc_output_tokens": output_tokens,
            "pmc_latency_ms": latency_ms,
            "pmc_attempt": attempt,
            "pmc_site": site,
            "pmc_subject": subject,
        },
    )


def stage_marker(events: list[dict], stage: str, *, end: bool = False) -> dict:
    """Append a stage boundary to the event log.

    Written by whoever drives the graph — the Streamlit stream loop, or the C9
    runner — not by an agent. Stage boundaries are a fact about the run, and
    only the driver knows them: a node's stream chunk arrives after the node
    has already finished.

    Bypasses the logger deliberately. There is no agent to attribute this to
    and nothing to format; the record shape lives here so replay has one
    schema to walk. This is what option (B) bought and what it cost: `events`
    is a run transcript, not purely what the handler collected.

    Marker pairs, not grouping by logger name, are what keep a revise pass
    distinct from the first drafter pass — two invocations, two marker pairs.
    """
    event = {
        "pmc_event": EVENT_STAGE_END if end else EVENT_STAGE_START,
        "pmc_stage": stage,
    }
    events.append(event)
    return event


class TelemetryHandler(logging.Handler):
    """Collects pmc_* telemetry; optionally paints it live.

    Two consumers, one class. The Streamlit app passes a sink so a repair fire
    appears the instant it fires — mid-node, while the graph is still inside a
    ~60s model call and no stream chunk has been emitted. C9 constructs it with
    no sink and reads the event list after the run.

    `sink` is a callable, not a container: this module must not import
    streamlit. The UI supplies a closure that writes into whatever stage
    container is currently open, and re-points it as stages advance.

    `events` is supplied by the caller rather than owned here because Streamlit
    rebuilds this handler on every script rerun. A handler that owned its list
    would start empty each time and the transcript would vanish on the first
    widget interaction.

    emit() must never raise into the observed path. logging.Handler.handle
    wraps emit in try/finally, not try/except, so an exception here propagates
    back to the logger.warning() call site inside the repair loop, out of
    draft_prd, into prd_node's except Exception -> STEP_ERROR -> END. A
    telemetry fault would kill the run it was watching. handleError() is the
    stdlib's own convention for this — StreamHandler.emit does exactly this.
    """

    def __init__(self, events: list[dict] | None = None, sink=None):
        super().__init__()
        self.events = events if events is not None else []
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = {
                k: v for k, v in record.__dict__.items() if k.startswith("pmc_")
            }
            event["logger"] = record.name
            event["message"] = record.getMessage()
            self.events.append(event)
            if self.sink is not None:
                self.sink(event)
        except Exception:
            self.handleError(record)
