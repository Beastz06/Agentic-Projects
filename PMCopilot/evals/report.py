"""Aggregate scored runs into the numbers behind results_v1.md.

Two kinds of fact, deliberately not mixed:

  SCORES come from every run supplied. One run cannot separate a real quality
  change from judge sampling noise, so scores stay per-run with the spread
  visible rather than collapsed into a single mean.

  COST AND LATENCY come only from runs carrying telemetry. results_v1.json
  predates instrumentation -- a valid score sample, never a cost sample.
  Attaching one run's spend to another run's scores would be invisible in
  the output and wrong.

Prices live here and nowhere else. A scored run records what happened; a
price is a fact about the world today. Sonnet 5 is the standing proof: its
introductory rate expires 2026-08-31, so reproducing an unchanged fixture
costs a different amount in September.
"""
import argparse
import json
import statistics as st
import matplotlib
import matplotlib.pyplot as plt
import os

matplotlib.use("Agg")

# USD per million tokens, (input, output). Verified 2026-08-04.
PRICES_USD_PER_MTOK = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),  # introductory; $3/$15 from 2026-09-01
}

# results_v1.json predates run_label. Amending a committed record to add a
# field is the one thing "records are appended, never updated" forbids, so
# the label is supplied by the reader -- same reasoning as the price table
# above. Keyed on the path as passed on the command line.
LABEL_OVERRIDES = {
    "evals/results_v1.json": "baseline",
}

DIMENSIONS = ["hallucination", "grounding", "completeness", "ac_quality"]
CHART_DIR = "evals/charts"

# Fixed dimension colours so the two charts, and every future report, use one
# legend. Assigned by evidence assignment rather than by score: the two
# retrieved-issues dimensions share a family, the other two are separate.
DIM_COLOR = {
    "hallucination": "#1f4e79",  # retrieved_issues
    "completeness": "#5b9bd5",  # retrieved_issues
    "grounding": "#c55a11",  # source_findings
    "ac_quality": "#7f7f7f",  # none
}

REPORT_PATH = "evals/results_v1.md"

# From PRD.md, held here rather than imported so the report states the
# committed claim even if run_evals.py's copy drifts. A duplicated constant
# is the lesser evil: the alternative is a report that silently reframes
# the bar it is reporting against.
TARGETS = {
    "hallucination": (5.0, "all score 5 (mean 5.0, zero below 5)"),
    "grounding": (5.0, "all score 5 (mean 5.0, zero below 5)"),
    "completeness": (4.0, "mean >= 4.0"),
    "ac_quality": (4.5, "mean >= 4.5"),
}


def verdict(means: list[float], floor: float) -> str:
    """Worst observation decides, not the mean of observations.

    A pass bar is a claim about the system. Claiming it on a favourable draw
    is the same error as publishing only repaired numbers -- it fits the
    verdict to the sample. The spread is reported beside this so a reader
    sees how close the call was.
    """
    return "MEETS" if min(means) >= floor else "MISSES"


def chart_cost_per_scenario(calls: list[dict], path: str) -> None:
    """Cost per scenario, stacked by dimension.

    Stacked rather than grouped because the question is where a scenario's
    spend goes, not how four independent series compare. The segment heights
    carry the finding: the two retrieved-issues dimensions dominate every
    bar, because evidence assignment -- not scenario difficulty -- sets cost.
    """
    stages = list(dict.fromkeys(c["stage"] for c in calls))
    fig, ax = plt.subplots(figsize=(11, 6))
    bottoms = [0.0] * len(stages)
    for dim in DIMENSIONS:
        vals = [
            sum(cost_usd(c) for c in calls
                if c["stage"] == s and c["pmc_subject"] == dim)
            for s in stages
        ]
        ax.bar(range(len(stages)), vals, bottom=bottoms,
               label=dim, color=DIM_COLOR[dim], width=0.7)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([s[:34] for s in stages], rotation=40,
                       ha="right", fontsize=8)
    ax.set_ylabel("USD")
    ax.set_title("Judge cost per scenario, by dimension")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_latency_per_dimension(calls: list[dict], path: str) -> None:
    """Median latency per dimension, y-axis anchored at zero.

    Anchored deliberately. The spread is ~7s on a ~27s base; an autoscaled
    axis would start near 20s and render a 25% difference as a fourfold one.
    Read against the cost chart, the point is the ABSENCE of a matching
    spread: hallucination and completeness carry ~8x the input of the other
    two and are not correspondingly slower.
    """
    fig, ax = plt.subplots(figsize=(7, 5))
    meds, errs = [], []
    for dim in DIMENSIONS:
        ms = [c["pmc_latency_ms"] / 1000 for c in calls
              if c["pmc_subject"] == dim]
        meds.append(st.median(ms))
        errs.append([st.median(ms) - min(ms)], )
        errs[-1].append(max(ms) - st.median(ms))

    ax.bar(DIMENSIONS, meds,
           color=[DIM_COLOR[d] for d in DIMENSIONS], width=0.6,
           yerr=list(zip(*errs)), capsize=5, ecolor="#333333")
    ax.set_ylim(0, max(m + e[1] for m, e in zip(meds, errs)) * 1.15)
    ax.set_ylabel("seconds")
    ax.set_title("Judge latency by dimension: input size does not predict it")
    ax.tick_params(axis="x", labelsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def attribute(events: list[dict]) -> list[dict]:
    """Assign each model_call to the stage open when it fired.

    Carries the open stage as state rather than matching pairs. An unclosed
    final interval attributes correctly by construction -- nothing opened
    after it, so the calls belong to it. Two consecutive starts is a driver
    bug, not an ambiguity, so it raises rather than guessing.
    """
    stage, calls = None, []
    for e in events:
        kind = e.get("pmc_event")
        if kind == "stage_start":
            if stage is not None:
                raise ValueError(
                    f"stage {e['pmc_stage']!r} opened while {stage!r} was open"
                )
            stage = e["pmc_stage"]
        elif kind == "stage_end":
            stage = None
        elif kind == "model_call":
            calls.append({**e, "stage": stage})
    return calls


def cost_usd(call: dict) -> float:
    model = call["pmc_model"]
    if model not in PRICES_USD_PER_MTOK:
        raise SystemExit(
            f"no price for {model!r} -- add it to PRICES_USD_PER_MTOK"
        )
    p_in, p_out = PRICES_USD_PER_MTOK[model]
    return (call["pmc_input_tokens"] * p_in
            + call["pmc_output_tokens"] * p_out) / 1_000_000


def write_report(runs: list[dict], charts: dict, path: str) -> None:
    L = []
    add = L.append
    labels = [r["_label"] for r in runs]
    tel = [r for r in runs if r["_calls"]]

    add("# C9 eval report — PMCopilot v1\n")
    add(f"Fixture `{runs[0]['provenance']['fixture_commit'][:7]}`, "
        f"captured {runs[0]['provenance']['fixture_captured_at'][:10]}. "
        f"Drafter `{runs[0]['provenance']['agent_model']}`, "
        f"judge `{runs[0]['provenance']['judge_model']}`, K="
        f"{runs[0]['provenance']['retrieval_k']}.\n")
    add(f"Scores from {len(runs)} independent judge runs over the same "
        f"frozen fixture ({', '.join(labels)}). The fixture does not move "
        f"between runs, so any score difference is judge sampling variance "
        f"and nothing else. Cost and latency come from `{tel[0]['_label']}` "
        f"only — the baseline run predates instrumentation.\n")

    # ---- pass bars
    add("## Pass bars\n")
    add("| dimension | " + " | ".join(labels)
        + " | spread | cells moved | target | verdict |")
    add("|---|" + "---|" * (len(labels) + 4))
    for dim, (floor, text) in TARGETS.items():
        means, per_run = [], []
        for r in runs:
            vals = [s["dimensions"][dim]["score"] for s in r["scenarios"]
                    if s["dimensions"].get(dim, {}).get("score") is not None]
            means.append(st.mean(vals))
            per_run.append({s["topic"]: s["dimensions"][dim].get("score")
                            for s in r["scenarios"]})
        topics = [s["topic"] for s in runs[0]["scenarios"]]
        scorable = [t for t in topics
                    if any(p[t] is not None for p in per_run)]
        moved = sum(1 for t in scorable
                    if len({p[t] for p in per_run if p[t] is not None}) > 1)
        add(f"| {dim} | " + " | ".join(f"{m:.2f}" for m in means)
            + f" | {max(means) - min(means):.2f} | {moved}/{len(scorable)}"
            + f" | {text} | **{verdict(means, floor)}** |")
    add("\nVerdicts are taken from the worst run, not the mean across runs.\n")

    # ---- cost
    add("## Cost and latency\n")
    r = tel[0]
    calls = r["_calls"]
    add(f"One full run: {len(calls)} calls, "
        f"{sum(c['pmc_input_tokens'] for c in calls):,} input and "
        f"{sum(c['pmc_output_tokens'] for c in calls):,} output tokens, "
        f"**${sum(cost_usd(c) for c in calls):.2f}**, "
        f"{sum(c['pmc_latency_ms'] for c in calls) / 60000:.1f} minutes "
        f"wall clock.\n")
    add("| dimension | avg input | avg output | USD | median s | max s |")
    add("|---|---|---|---|---|---|")
    for dim in DIMENSIONS:
        c = [x for x in calls if x["pmc_subject"] == dim]
        ms = [x["pmc_latency_ms"] for x in c]
        add(f"| {dim} | {st.mean([x['pmc_input_tokens'] for x in c]):,.0f}"
            f" | {st.mean([x['pmc_output_tokens'] for x in c]):,.0f}"
            f" | {sum(cost_usd(x) for x in c):.2f}"
            f" | {st.median(ms) / 1000:.1f} | {max(ms) / 1000:.1f} |")

    add("\n### Per scenario\n")
    # The deliverable's core table: one row per scenario, scores from every
    # run, spend from the telemetry-bearing one. Scores and spend come from
    # different runs by necessity -- the baseline predates instrumentation --
    # and the column headers name which is which rather than eliding it.
    score_cols = " | ".join(f"{d[:4]} {lab[:4]}"
                            for d in DIMENSIONS for lab in labels)
    add(f"| scenario | band | {score_cols} | USD | median s |")
    add("|---|---|" + "---|" * (len(DIMENSIONS) * len(labels) + 2))
    for i, s in enumerate(runs[0]["scenarios"]):
        topic = s["topic"]
        cells = []
        for dim in DIMENSIONS:
            for run in runs:
                v = run["scenarios"][i]["dimensions"].get(dim, {}).get("score")
                cells.append("—" if v is None else str(v))
        sc = [c for c in calls if c["stage"] == topic]
        ms = [c["pmc_latency_ms"] for c in sc]
        add(f"| {topic} | {s['band']} | " + " | ".join(cells)
            + f" | {sum(cost_usd(c) for c in sc):.2f}"
            + f" | {st.median(ms) / 1000:.1f} |")

    def rel(p: str) -> str:
        # Relative to the report's own directory -- how GitHub and every
        # local previewer resolve image links. The separator swap is not
        # cosmetic: relpath returns backslashes on Windows, and markdown
        # reads a backslash as an escape, so the link silently dies.
        return os.path.relpath(p, os.path.dirname(path)).replace(os.sep, "/")

    add(f"\n![cost]({rel(charts['cost'])})")
    add(f"![latency]({rel(charts['latency'])})\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate scored runs.")
    ap.add_argument("runs", nargs="+", help="paths to results JSON files")
    args = ap.parse_args()

    runs = []
    for path in args.runs:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        r["_path"] = path
        r["_label"] = LABEL_OVERRIDES.get(
            path.replace("\\", "/"),
            r["provenance"].get("run_label", "unlabelled"),
        )
        r["_calls"] = attribute(r.get("telemetry", []))
        runs.append(r)

    labels = [r["_label"] for r in runs]
    print(f"runs: {labels}")
    for r in runs:
        n = len(r["_calls"])
        print(f"  {r['_label']:<14} {r['_path']:<34} "
              f"{'telemetry: ' + str(n) + ' calls' if n else 'NO TELEMETRY'}")

    # ---- scores across runs -------------------------------------------
    print("\nscores by dimension")
    print(f"{'dimension':<15}" + "".join(f"{l[:10]:>12}" for l in labels)
          + f"{'spread':>9}{'moved':>8}")
    for dim in DIMENSIONS:
        means, per_run = [], []
        for r in runs:
            vals = [s["dimensions"][dim]["score"] for s in r["scenarios"]
                    if s["dimensions"].get(dim, {}).get("score") is not None]
            per_run.append({s["topic"]: s["dimensions"][dim].get("score")
                            for s in r["scenarios"]})
            means.append(st.mean(vals))
        topics = [s["topic"] for s in runs[0]["scenarios"]]
        # Exempt cells have no score in any run. They are not "unmoved" --
        # they are outside the denominator. An exemption CHANGING between
        # runs would still read as unmoved here; that is unreachable while
        # completeness_exempt is a fixture field, and is why this stays a
        # count rather than a comparison.
        scorable = [t for t in topics
                    if any(p[t] is not None for p in per_run)]
        moved = sum(
            1 for t in scorable
            if len({p[t] for p in per_run if p[t] is not None}) > 1
        )
        print(f"{dim:<15}" + "".join(f"{m:>12.2f}" for m in means)
              + f"{max(means) - min(means):>9.2f}"
              + f"{moved:>5}/{len(scorable)}")

    # ---- cost and latency, telemetry-bearing runs only -----------------
    charts: dict[str, str] = {}
    for r in runs:
        if not r["_calls"]:
            continue
        calls = r["_calls"]
        print(f"\ncost and latency -- {r['_label']} ({len(calls)} calls)")
        print(f"{'dimension':<15}{'in':>10}{'out':>9}{'usd':>9}"
              f"{'p50 s':>8}{'max s':>8}")
        for dim in DIMENSIONS:
            c = [x for x in calls if x["pmc_subject"] == dim]
            if not c:
                continue
            ms = [x["pmc_latency_ms"] for x in c]
            print(f"{dim:<15}"
                  f"{sum(x['pmc_input_tokens'] for x in c):>10}"
                  f"{sum(x['pmc_output_tokens'] for x in c):>9}"
                  f"{sum(cost_usd(x) for x in c):>9.2f}"
                  f"{st.median(ms) / 1000:>8.1f}{max(ms) / 1000:>8.1f}")
        total_ms = sum(x["pmc_latency_ms"] for x in calls)
        print(f"{'TOTAL':<15}"
              f"{sum(x['pmc_input_tokens'] for x in calls):>10}"
              f"{sum(x['pmc_output_tokens'] for x in calls):>9}"
              f"{sum(cost_usd(x) for x in calls):>9.2f}"
              f"{'':>8}{total_ms / 60000:>7.1f}m")
        os.makedirs(CHART_DIR, exist_ok=True)
        c1 = f"{CHART_DIR}/cost_per_scenario_{r['_label']}.png"
        c2 = f"{CHART_DIR}/latency_per_dimension_{r['_label']}.png"
        chart_cost_per_scenario(calls, c1)
        chart_latency_per_dimension(calls, c2)
        print(f"\nwrote {c1}\n      {c2}")
        if not charts:  # first telemetry-bearing run, matching tel[0] below
            charts = {"cost": c1, "latency": c2}

    if charts:
        write_report(runs, charts, REPORT_PATH)
        print(f"      {REPORT_PATH}")


if __name__ == "__main__":
    main()
