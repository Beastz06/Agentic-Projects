# C8 UI Runs Part 1

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
`{'prd': ...}` envelope. Not wrapper-nesting, not in the characterized
set. n=1; logged, no action per parked-items discipline.

## Unverified
Whether the revise pass dropped the tool-calling story and whether
`out_of_scope` absorbed it unprompted was not checked — the PRD renders only
at the gate, and the `done` panel shows ids. The 2-for-2 unprompted-bookkeeping
finding stands at 2-for-2. Notion page above holds the approved PRD;
answerable there or by the PRD repository view.

---

## C8 Part 2 — views over a session ledger

Four runs. Two revise runs (`tool calling and function calling`) to verify the
PRD repository; three approve-only runs on distinct topics to populate the
roadmap. Model `claude-sonnet-5` throughout, corpus unchanged.

### Ledger contract

Predicted **20 records** for an approve-only run and hit it exactly, including
the per-node breakdown. Derivation: one record per *key* in each node's return
dict, summed over node *executions*.

- 10 worker executions x 2 keys = 20. Supervisor executes 11 times and
  contributes 0 (returns `{}`).
- Summarizer fans out one audience per superstep: 3 executions, 3 `digests`
  records — visible in the ledger as increments, not one list.
- `approval_gate` appears **once**, post-resume. The interrupted execution
  emits `__interrupt__` (a tuple, not a return dict) and contributes nothing.
- **The count is retry-invariant.** The drafter's repair loop runs inside
  `prd_node`, so retries produce no extra updates chunks. 20 holds at 0, 1, or
  2 retries. Events count *attempts*; the ledger counts *outcomes*.
- Half the ledger (10 of 20) is `current_step` — routing bookkeeping no view
  reads. Noise by construction, left in rather than filtered at capture.
  
---

### Revise behaviour

**The revise pass is a full redraft, not a patch.** Problem statement rewritten,
every story and AC reworded, success metrics renamed and recounted, risks
reworded with severities moving. On the verified run: user stories 7 -> 6,
ACs 7 -> 6, `out_of_scope` count unchanged at 4 with **all four entries
different**.

This reframes the "unprompted bookkeeping" finding. The cut content does surface
in `out_of_scope`, but via regeneration of the whole list — not by appending a
note to an existing one. The prior 2-for-2 was likely the same mechanism read as
something more deliberate.

**Instrument error, corrected mid-session.** Run 1's feedback said "that's a
separate workstream"; the model's `out_of_scope` entry echoed "tracked as a
separate workstream." Phrasing leak, not unprompted behaviour. Run 2 stripped
the justification to bare "Cut anything about streaming tool-call responses."
`out_of_scope[0]` still absorbed it, with no echo. **Unprompted bookkeeping
3-for-3, one instance contaminated, behaviour sound.**

**New finding — the model bookkeeps risk POLARITY, second order.**
- Draft risk: *adding `tool_call_id` to streaming events may require breaking
  changes* — a risk of DOING the work.
- Revision risk: *LOW — excluding streaming tool-call work may leave the
  correlation gap unresolved, could resurface as a blocker* — a risk of NOT
  doing it.

It did not delete the streaming risk alongside the streaming story; it inverted
it to match the new scope. Stronger evidence than the `out_of_scope` line: a
list entry is bookkeeping, a re-polarised risk is reasoning about the
consequence of the edit.

---

### Gate payload gap

`_prd_review_payload` projects **five** fields (theme, problem_statement,
target_user, user_stories, acceptance_criteria). The PRD carries **eight**.
`out_of_scope`, `risks`, and `success_metrics` have never been visible at the
gate on any run in any session — which is why the parked revise-content question
was unanswerable from the gate screen by construction, not by oversight. The
repository view closed it in one run.

---

### Planner, first multi-item invocation

Three PRDs, one `plan()` call. `depends_on` forced empty at score time, so
`_score` saw all three together.

| item | stories | effort | impact | quarter |
|---|---|---|---|---|
| Harden Tool/Function-Calling Pipeline | 6 | 8 | 5 | Q1 |
| Robust Streaming & Chunk Handling | 5 | 8 | 5 | Q1 |
| Reliable Token Counting & Usage Metadata | 5 | 8 | 4 | Q2 |

**Effort did not differentiate. 8/8/8 — one rung of six on the Fibonacci
scale**, with near-identical rationale templates ("*N* distinct user stories
spanning ... represent a broad, multi-subsystem effort"). C4
scoring-differentiation: answered, NEGATIVE.

**Consequence: the quarter assignment is arithmetic on a constant.** At
`DEFAULT_BUDGET=16` with every item at 8, `_assign_quarters` packs exactly two
per quarter. A 4th PRD opens Q2, a 5th opens Q3, regardless of content. Board
shape is determined by item COUNT, not relative size.

**Impact DID differentiate — 5/5/4 — and on evidence density.** The 4 went to
the token-counting PRD, whose own effort rationale notes "evidence for some
sub-issues is thin" and whose top risk names three of five pain points as
single-issue-backed. Asymmetry worth carrying to C9: impact scoring is
responsive to evidence density; effort scoring is not.

**Zero dependency detections across three overlapping PRDs.** The tool-calling
PRD's own stories cover streaming tool-call payloads — the streaming PRD's
territory. `depends_on` empty on all three. C4 dependency positive-path remains
unexercised, now with a suspicious negative result against it.

---

### Withdrawn: Risk-collapse count

Claimed no-fire on two runs by reading the absence of a warning line. **That
inference does not hold.** `render_events` recreates each stage as
`st.status(..., expanded=False)`, so on replay a repair line sits inside a
collapsed expander. No-fire and fire-hidden are indistinguishable in every
capture taken. The C8 Part 1 count of 4-for-4 stands; this session adds nothing.
Count withdrawn pending a proper instrument (`ss.events` scan, not visual
inspection).

**The finding underneath is the useful one: the paint-on-emit guarantee
established in C8 Part 1 does not survive replay.** Retries are visible live and
invisible at rest. For a recruiter-facing demo that is backwards — the repair
loop is the most interesting behaviour in the system and a finished run shows no
trace of it. Same family as the six empty stage expanders.

---

### UI pattern: unconstrained prose in narrow containers

Three instances in one session, same root cause — model-authored free strings
rendered in width-constrained widgets:

1. `SuccessMetric.target` in `st.metric` — 9 of 9 truncated; one value
   overlapped its own caption. Fixed: `st.table` (not `st.dataframe`, which has
   fixed row heights and would truncate `definition` instead).
2. `EffortScore.rationale` / `ImpactScore.rationale` in a quarter-width column —
   2-3 words per line. Fixed: `st.popover`, which escapes the column.
3. `RoadmapItem.title` in a quarter-width column — wraps to four lines.
   Unfixed, cosmetic.

Rejected: constraining `target` length in the schema. A length limit on a
model-judged prose field pressures invention of fake scalars — the C3
fabrication trap.

---

### Streamlit facts verified

- **`st.session_state` survives a RERUN, not a browser REFRESH.** A refresh
  opens a new session: empty ledger, phase back to `idle`. Cost one full run
  when acted on incorrectly. The cold-load / refresh-recovery parked item is
  now EVIDENCED, not speculative.
- Every `st.tabs` body executes on every script run; only the active one is
  visible. So nothing expensive can live in a tab body, and an unconditional
  `plan()` call there would fire on every rerun.
- `run_stream` must be called inside `with tab_run:` — it creates `st.status`
  via bare `st.` calls, which attach to the ambient container.
- `expanded` applies only at widget CREATION. An expander whose label is
  unchanged keeps its current state across reruns; flipping `expanded` cannot
  close an already-open card.
- No programmatic tab focus in the stable API — which is what killed the option
  of moving the gate to the PRDs tab.
- An uncaught exception in a tab body kills the whole page, including the Run
  tab mid-gate. `plan()` is wrapped for this reason (`_assign_quarters` raises
  past four quarters).
  
---

## C8 Part 3 — digest viewer

Two approve-only runs, distinct topics: "streaming behavior and chunk handling"
(`ui-20260730T171558Z`) and "token counting and usage metadata"
(`ui-20260730T172159Z`). Ledger empty at session start — `session_state` does
not survive a browser session, so the prior session's PRDs were unrecoverable
while their checkpoints persisted. Second evidenced instance of the cold-load
gap.

### Verified

| behaviour | result |
|---|---|
| Empty state before any digest | renders |
| Partial-run pending caption during fan-out | renders |
| Three sections, `AUDIENCES` order, `3 of 3` caption | correct |
| Auto-advance on the complete audience set | fires |
| Latch — manual selection survives subsequent reruns | holds |

The latch is the only one a simulated trace could not establish. Written
unconditionally, the auto-advance would overwrite the selection on the rerun
the user's own click triggers, making every run but the newest unreachable.
Streamlit has no events; "do X when E happens" must be written as "do X when
E differs from what I last acted on."

---

### Audience differentiation — the claim the view exists to make

Validated on both runs. Engineering names symbols (`ClearToolUsesEdit`,
`SummarizationMiddleware`, tiktoken, langchain-openai); executive abstracts to
cost tracking and asks for approval; customer is second-person and asks for
reports. Three genuinely different documents from one PRD, visible without a
click — which is why the layout is stacked rather than tabbed.

---

### grounded_in degeneracy, confirmed visually

Every claim in both runs grounds to the single theme string. Structural, not
incidental: `prds` is a plain channel holding one PRD, so `summarize()`
receives a one-element theme set and membership is trivially satisfiable.
C9's grounding dimension is near-degenerate on single-PRD scenarios.

---

### Claim volume tracks input theme count

C5 measured eng 17/17, exec 9→11, customer 13→15 — over a **three-theme**
input. Single-PRD runs here show roughly four to six. Single-PRD C9 scenarios
hand the judge a materially thinner index. Counts not read exactly; popovers
scroll.

---

### Schema identifier in reader-facing prose

Engineering digest, token-counting run: "Depends_on is nothing, so this can
proceed independently of other roadmap items." A raw field name addressed to
a person.

---