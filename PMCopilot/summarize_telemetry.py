"""Summarize a telemetry dump: per-segment and per-logger token totals.

Segments come from stage_marker pairs written by the driver; the model calls
between a start and its end belong to that segment. Calls outside any pair —
the gate interpreter, once instrumented — are reported as 'unsegmented'.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def summarize(path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    events = doc["events"]

    stage = None
    by_stage = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "ms": 0})
    by_logger = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0})
    repairs = []
    unwraps = []

    for e in events:
        kind = e.get("pmc_event")
        if kind == "stage_start":
            stage = e["pmc_stage"]
        elif kind == "stage_end":
            stage = None
        elif kind == "model_call":
            key = stage or "unsegmented"
            by_stage[key]["calls"] += 1
            by_stage[key]["in"] += e["pmc_input_tokens"]
            by_stage[key]["out"] += e["pmc_output_tokens"]
            by_stage[key]["ms"] += e["pmc_latency_ms"]
            lg = e["logger"]
            by_logger[lg]["calls"] += 1
            by_logger[lg]["in"] += e["pmc_input_tokens"]
            by_logger[lg]["out"] += e["pmc_output_tokens"]
        elif kind == "repair_fire":
            repairs.append((e["logger"], e.get("pmc_attempt"), e.get("pmc_defect_origin")))
        elif kind == "envelope_unwrap":
            unwraps.append((stage or "unsegmented", e.get("pmc_wrapper_key")))

    print(f"\n=== {path.name} — topic={doc['topic']} ===")
    print(f"thread: {doc['thread_id']}  captured: {doc['captured_at']}")

    print("\nSEGMENT              calls      in     out      ms")
    total_in = total_out = total_calls = 0
    for name, v in by_stage.items():
        print(f"{name:<20}{v['calls']:>6}{v['in']:>8}{v['out']:>8}{v['ms']:>8}")
        total_in += v["in"]
        total_out += v["out"]
        total_calls += v["calls"]
    print(f"{'TOTAL':<20}{total_calls:>6}{total_in:>8}{total_out:>8}")

    print("\nLOGGER                       calls      in     out")
    for name, v in sorted(by_logger.items()):
        print(f"{name:<28}{v['calls']:>6}{v['in']:>8}{v['out']:>8}")

    print(f"\nrepair fires: {len(repairs)}")
    for lg, attempt, origin in repairs:
        print(f"  {lg} attempt={attempt} origin={origin}")

    print(f"envelope unwraps: {len(unwraps)}")
    for seg, key in unwraps:
        print(f"  {seg}: nested under {key!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize telemetry dumps.")
    parser.add_argument("paths", nargs="+", help="One or more telemetry JSON dumps.")
    args = parser.parse_args()
    for p in args.paths:
        summarize(Path(p))


if __name__ == "__main__":
    main()
