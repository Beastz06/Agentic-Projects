# Eval suite

LLM-as-Judge scoring of drafted PRDs on four dimensions, 1–5. Opus judges Sonnet's
output, so the judge's blind spots don't correlate with the drafter's. Four isolated
judge calls per PRD rather than one shared call, to prevent halo effect across
dimensions.

## Read this first: filenames and labels do not agree

Filenames count **captures**. Labels inside the files count **prompt generations**.
They diverged at the second prompt revision and were never resynced.

| file | prompt generation | fixture commit | n | what it is |
|---|---|---|---|---|
| `fixture_v1.json` → `results_v1.json` | **v1** | `c19d36db` | 10 | baseline |
| `fixture_v1.json` → `results_v1_run2.json` | **v1** | `c19d36db` | 10 | same fixture, judged a second time |
| `fixture_v2.json` → `results_v2.json` | **v2a** | `f11d5bd0` | 10 | after the atomicity example |
| `fixture_v3.json` → `results_v3.json` | **v2b** | `cb46350b` | 9 | after the vagueness example |
| `fixture_v4.json` → `results_v4.json` | **v2b** | `6cef80df` | 10 | *re-capture at an unchanged prompt* |

Two consequences worth stating plainly:

- The headline result (ac_quality 4.33) is in **`results_v3.json`**, not `results_v2.json`.
- **`v4` is not a fourth prompt generation.** `SYSTEM_PROMPT` is byte-identical between
  `cb46350b` and `6cef80df`. It is a second capture of v2b, drafted under a schema fix
  that removed a repair loop. It exists to test reproducibility, not to advance the series.

`fixture_v3.json` holds 9 scenarios because `documentation gaps` exhausted its retry
budget during that capture and produced no PRD. The schema fix recovered it, which is
why v4 is back to 10. Cross-generation comparisons use the shared nine.

## Two kinds of noise, and only one of them was measured

`results_v1.json` and `results_v1_run2.json` judge the **same frozen fixture** twice.
The spread across them — at most 0.20 on any dimension mean, and 0.00 on ac_quality —
is **judge noise**. It describes how reproducibly the judge scores a fixed artifact.

It says nothing about how reproducibly the *drafter* produces artifacts. That quantity
is visible only by comparing `results_v3.json` and `results_v4.json`, which share a
prompt and differ by a re-draft: ac_quality 4.33 → 3.00, a swing of 1.33. That capture
also carries the schema fix, so 1.33 is an upper bound on redraft noise rather than an
estimate of it. Separating the two needs at least two captures on each side of the fix;
it has not been done.

Any delta quoted between prompt generations carries redraft noise of unknown size.
The judge-noise figure does not license those deltas and should not be cited for them.

## Provenance is weaker than it looks

`provenance.commit` in each fixture records **HEAD at capture time**. It does not record
whether the working tree was clean, and there is at least one confirmed case where it
was not: the schema fix was live in the tree during the v4 capture but was committed
afterward, so it appears nowhere in `git diff cb46350b 6cef80df`.

**A fixture commit therefore identifies when a capture ran, not the code that ran it.**
Adding a dirty-tree flag and a hash of the drafter prompt is the first fix this suite
needs.

## Files

- `fixture_v*.json` — captured PRDs plus per-call telemetry. Input to the judge.
- `results_v*.json` — per-scenario scores, per-dimension findings, judge provenance.
- `results_v1.md` — rendered report. Covers v1 only; the renderer has no awareness of
  later runs.
- `telemetry_*.json` — full-pipeline model-call records from gate-driver runs, used for
  the cost measurement rather than for scoring.
- `judge_prompt_template.md`, `rubrics.py` — scoring rubric and dimension anchors.

## Reproducing

```
# capture a fixture (drafts PRDs against the current code and prompt)
uv run python capture_fixture.py --out evals/fixture_vN.json

# judge an existing fixture (no drafting; safe to re-run)
uv run python -m evals.run_evals --fixture evals/fixture_vN.json \
    --out evals/results_vN.json --label <label>
```

Judging is non-destructive and cheap to repeat. Capturing is not: it re-drafts every
scenario, and as the v3/v4 pair shows, a re-capture at an unchanged prompt can move a
dimension mean by more than a prompt revision did.
