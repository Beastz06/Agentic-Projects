# C8 UI Runs — Day 29

Two full runs through the Streamlit app (`app.py`), langchain corpus, topic
"streaming behavior and chunk handling" both times. Not part of the Day 28
five-run series — different driver, different purpose. Recorded because the
drafter fired four times and exposed a dimension the integration checkpoint
never measured.

## Run A — approve-only (probe_debug.py driver, gate not reached)
- drafter: 2 fires, wrapper-nesting `{'prd': {...}}` both attempts, identical
  error text. Succeeded on attempt 3.
- Note: probe run, stopped at gate. No MCP traffic.

## Run B — revise-then-approve (app.py, full pipeline)
- thread: ui-20260727T184214Z
- terminal outcome: full. jira #8, notion 45f69e8010914e65a956ca9b6c5d293c,
  slack ts 1785177996.073998, 1 roadmap item, 3 digests, zero errors,
  zero degrade activations.
- revise feedback: named the cluster to drop (tool-calling argument assembly),
  not a criterion — per the Day 28 clustering-invariance lesson.
- drafter invocation 1: 1 fire — **Risk-collapse**. Bare string into `risks.0`
  while writing the thin-evidence caveat. Succeeded on attempt 2.
- drafter invocation 2 (revise pass): 2 fires — wrapper-nesting, identical
  error text both attempts. Succeeded on attempt 3.
- summarizer: 0 fires. planner: 0 fires. discovery: 0 fires.

## Retry depth — new dimension

| fire | mode | attempts to success |
|---|---|---|
| A.1 | wrapper-nesting | 3 |
| B.1 | Risk-collapse | 2 |
| B.2 | wrapper-nesting | 3 |
| B.3 | wrapper-nesting | 3 |

Three of four consumed the full `MAX_RETRIES = 2` budget and succeeded on
attempt 3 — one failure short of `STEP_ERROR -> END`. Day 28 banked
"self-heals every time" but measured fire *rate* only; depth was never
recorded. This is a measurement gap, not a behavioral change.

Also: attempt 1 of one fire reported 3 validation errors, attempt 2 reported 1.
The repair loop fixed two of three and left one — **partial repair**. Day 20
set the budget at 2 on the premise that "if the corrected attempt fails again,
the model is demonstrating it can't satisfy the contract." Partial repair
falsifies that binary; attempt 2 was making progress, not failing to comply.

Do not tune `MAX_RETRIES` on n=4. C9 measures it.

## Risk-collapse — 4-for-4, trigger refined
Fired on a *dense* topic (three distinct failure modes, multiple stories).
The model wrote a thin-evidence caveat anyway, so the correlated trigger is
the caveat itself, not evidence density. Best-evidenced open fix in the ledger:
`Severity -> schemas/common.py`.

## New specimen — top-level required-field omission
`target_user` missing, `input_value={'theme': 'streaming beha...` — no
`{'prd': ...}` envelope. Not wrapper-nesting, not in the Day 28 characterized
set. n=1; logged, no action per parked-items discipline.

## Unverified
Whether the revise pass dropped the tool-calling story and whether
`out_of_scope` absorbed it unprompted was not checked — the PRD renders only
at the gate, and the `done` panel shows ids. The 2-for-2 unprompted-bookkeeping
finding stands at 2-for-2. Notion page above holds the approved PRD;
answerable there or by the Day 30 PRD repository view.