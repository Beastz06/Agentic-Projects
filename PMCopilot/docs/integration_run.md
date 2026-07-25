# Integration Run — Full-System Checkpoint

Five end-to-end runs against the 200-issue langchain corpus, representative
topic sampling. Gate protocol: approve-only on runs 2–4; revise-then-approve
on runs 1 and 5 (dense vs. thin evidence, controlled comparison of the revise
loop). Model: claude-sonnet-5. Graph: 11 nodes / 18 edges.

Outcome taxonomy: terminal outcome (full / degraded / failed) plus
sub-observations per run. "Degraded" = jira filed but notion or slack degrade
path fired; run completed with error logged.

| Run | Topic | Gate protocol | Terminal outcome |
|-----|-------|---------------|------------------|
| 1 | tool calling reliability | revise → approve | |
| 2 | streaming behavior and chunk handling | approve | |
| 3 | agent middleware and execution | approve | |
| 4 | structured output and schema validation | approve | |
| 5 | token counting and usage metadata | revise → approve | |

---

### Run 1 — topic: "tool calling reliability"
- thread_id: gate-demo-20260723T210726Z (attempt 1, failed at planner) →
  gate-demo-20260723T214339Z (attempt 2, full protocol replay, completed)
- terminal outcome: full (attempt 2); attempt 1 = failed (planner, pre-fix)
- prediction (pre-run): full outcome; drafter repair fire on pydantic.
  Post-gate prediction (attempt 1): planner failed, API-error class.
- prediction vs actual: drafter fire — correct, twice (wrapper-nesting both
  attempts, not a novel mode). Planner API-error class — correct, but the
  interesting part was unpredicted: deterministic 400 (schema property-key
  charset), not transient. First multi-word topic in system history exposed
  it; all five slate topics would have failed identically. Fix: dep-tool
  schema restructured, themes moved from property keys to values
  (integration-checkpoint find #1). Revise-loop prediction (attempt 1):
  stories→~3, statement shrinks, evidence={36411,36349,36679,35514} —
  evidence exact, statement correct, count off (4: drafter split control-flow
  cluster into two stories, symmetric with the parser/streaming split).
  Attempt 2 revise prediction: NOT MADE — discipline lapse, logged.

Sub-observations:
- repair-loop fires: discovery=0 drafter=1 (attempt 1: wrapper-nesting;
  attempt 2: wrapper-nesting — 4th and 5th live specimens) planner=0
  (post-fix; dependency call cleared new array schema clean)
- stop_reason trips: none observed
- gate: revise → approve, both attempts. Same verbatim directive
  ("keep dense evidence, drop the rest") produced different surviving sets:
  attempt 1 cut HITL (single-issue); attempt 2 kept HITL (drafter had
  pre-merged 36411 into it, making it two-issue dense) and cut 36349
  entirely. Finding: a density directive delegates the cut to the draft's
  clustering; feedback that names issues, not criteria, would be
  clustering-invariant.
- degrade paths: notion=ok slack=ok
- retrieval eyeball: strong for this topic's evidence
- artifacts ground-truth: jira #3 = body is the post-revise problem_statement verbatim — no paraphrase drift, and correctly the revised text rather than the pre-gate draft;
  
  notion 7f78a7bda916464bbc2cc4bf8a076ba9 = No Pydantic reprs anywhere. All eight sections present;
  
  slack ts 1784843325.731400 = composed exec prose, not raw digest. Carries the evidence caveat ("each with only a single reported instance"), the risk framing (state-checkpointing compatibility), roadmap context (Q1, moderate effort/high impact, no dependencies), and closes with an ask.
- wall-clock: post-approve segment ~45s (est.); pre-gate → first PRD ~35s
  (est.).
  
--- 

### Run 2 — topic: "streaming behavior and chunk handling"
- thread_id: gate-demo-20260723T220759Z
- terminal outcome: full
- prediction (pre-run): no drafter fire; no errors; all artifacts generated.
- prediction vs actual: exact. First untouched run of the day — zero repair
  fires anywhere, wrapper-nesting streak broken at 5 (was 5-for-5 on drafter
  invocations before this run).

Sub-observations:
- repair-loop fires: discovery=0 drafter=0 planner=0 (array schema clean on
  first fresh topic)
- stop_reason trips: none
- gate: clean approve, no revision
- degrade paths: notion=ok slack=ok
- retrieval eyeball: strong — 8 distinct issues across 5 stories, four
  two-issue clusters, no repeated pair. Densest evidence set of the day so
  far. Note: 35514 also appeared in run 1 (tool-call fragment execution) —
  first cross-topic evidence reuse; legitimate overlap, not retrieval defect.
- artifacts ground-truth: jira #4 = problem_statement verbatim, no drift;
  notion 9e2d143b5cd64cf282698f7b9d970418 = all eight sections, readable
  prose, no reprs; slack ts 1784844596.161956 = composed exec prose carrying
  thin-evidence caveat, latency/compatibility tradeoffs, effort 8/10 impact
  4/5, closes with an ask. No jargon or id leakage.
- wall-clock: invoke → PRD render 0:43; approve → final report 1:02

---

### Run 3 — topic: "agent middleware and execution"
- thread_id: gate-demo-20260723T222006Z
- terminal outcome: full
- prediction (pre-run): NOT MADE — second lapse today; logged. The placed-
  but-unstated hypothesis (37195 reappears) would have been WRONG: 37195
  absent; instead 37093 + 35836 reappeared from run 1's cut list and 35574
  crossed over from the authentication run.
- prediction vs actual: n/a (no prediction). Unpredicted finding: three-run
  evidence reuse — the corpus has a connected agent-boundary cluster
  (HITL safety, result injection, header forwarding) that surfaces under
  multiple topic framings. C9-relevant for threshold tuning.

Sub-observations:
- repair-loop fires: discovery=0 drafter=1 (wrapper-nesting, 6th specimen —
  now 6-of-7 drafter invocations today; run 2's clean pass is the outlier)
  planner=0 summarizer=2 (customer + exec, one retry each — FIRST digest-
  level fires in system history; retry message doesn't print the defect,
  unlike drafter/planner repair prints → logging-consistency gap, parked)
- stop_reason trips: none
- gate: clean approve, no revision
- degrade paths: notion=ok slack=ok
- retrieval eyeball: mixed  — cluster count with issue-per-cluster spread (from the PRD: 4 singletons, 2 two-issue clusters, 8 distinct issues)
- artifacts ground-truth: jira #5 = verbatim, no drift; notion
  66b9e68e27b7449086676e053a066afc = all eight sections, readable, no reprs;
  slack ts 1784845346.143369 = composed, elevates the HITL safety bug as
  priority within the bundled ask — composer-level prioritization judgment,
  correct. No leakage.
- wall-clock: invoke → PRD render 1:08; approve → final report 1:02.
  (Pre-gate time nearly doubled vs run 2's 0:43 — consistent with the
  repair retry adding a full drafter call. Post-approve stable at ~1:02
  despite two summarizer retries — suggests retries are cheap relative to
  the MCP session spawns.)

Content note: feature-request skew visible and drafter tone followed it —
problem_statement describes missing capabilities, not broken behavior; 4 of
6 stories are singletons (~9 distinct issues). "Requests draft differently
than defects" hypothesis held, unpredicted.

---

### Run 4 — topic: "structured output and schema validation"
- thread_id: gate-demo-20260723T223319Z
- terminal outcome: full
- prediction (pre-run): drafter may fire; summarizer should not; evidence
  centers on Pydantic schemas and retry loops.
- prediction vs actual: all three correct. Nuance on #3 — Pydantic landed
  everywhere (ghost fields v__args, RootModel unions, schema construction),
  but "retry loops" landed only partially: 36603 asks for retry *guidance*
  on parse failure, not repair-loop machinery. Own-build bias confirmed:
  the corpus's structured-output pain is provider-conformance, not agent
  repair loops.

Sub-observations:
- repair-loop fires: discovery=0 drafter=1 planner=0 summarizer=0
  IMPORTANT: fire was Risk-collapse (bare string into risks.0), NOT
  wrapper-nesting. 2nd specimen of this mode; both instances collapsed
  Risk(description, severity) while writing the thin-evidence caveat
  ("Evidence base is thin: ..."). Correlated failure, not random —
  the model drops severity specifically on that risk. Elevates the parked
  Severity→schemas/common.py item.
- stop_reason trips: none
- gate: clean approve, no revision
- degrade paths: notion=ok slack=ok
- retrieval eyeball: strong (on-target by locked standard — all 8 issues
  belong in a structured-output PRD). Depth: 8 distinct issues / 5 clusters
  — one 3-issue (schema generation artifacts), one 2-issue, three
  singletons. Densest single cluster of the day.
- artifacts ground-truth: jira #6 = verbatim, no drift; notion
  843132102b694951af56d06f1cfc0f7f = all eight sections, readable, no reprs;
  slack ts 1784846133.442264 = composed, carries thin-evidence caveat and
  the external-provider-dependency risk as the headline caveat. No leakage.
- wall-clock: invoke → PRD render 1:00; approve → final report 0:54.

---

### Run 5 — topic: "token counting and usage metadata"
- thread_id: gate-demo-20260723T224446Z
- terminal outcome: full
- prediction (pre-run): drafter no-fire; summarizer no-fire; retrieval thin.
- prediction vs actual: drafter WRONG twice over — Risk-collapse pre-gate
  (3rd specimen) AND wrapper-nesting on the revise pass (7th specimen);
  first run to hit both modes. Summarizer WRONG — eng fired once (2nd
  occurrence ever; run 3 was customer+exec — no audience pattern yet).
  Thin: correct. Honest note: after a 6-of-7 drafter fire rate, predicting
  no-fire was base-rate neglect, not inference.
  Revise prediction: survivors {35558, 38229, 37815, 38249} — EXACT.
  Story count "goes down" — wrong in the interesting way: 4→4. The drafter
  compensated for the cut by synthesizing a bridging story citing all four
  surviving ids across both pain points (indices [1,4]) — recombination
  behavior dense topics never showed. Legitimate story (counting feeds
  eviction), but post-revise story counts are not comparable across
  density regimes.
- Risk-collapse correlation now 3-for-3: fires only while writing the
  thin-evidence caveat risk. Deterministic-ish semantic trigger, not random.

Sub-observations:
- repair-loop fires: discovery=0 drafter=2 (Risk-collapse pre-gate;
  wrapper-nesting on revise) planner=0 summarizer=1 (eng)
- stop_reason trips: none
- gate: revise → approve, verbatim run 1 directive. Compliance identical to
  run 1: both singletons (37754, 36661) cut, statement shrunk and
  self-documenting. Dense-vs-thin comparison: directive behaves identically;
  outcomes differ via recombination (above).
- degrade paths: notion=ok slack=ok
- retrieval eyeball: on-target, thin depth — 7 issues / 4 clusters (two
  2-issue, two singletons). Rating settled after working the locked
  standard: initial "off-target" claim (36661) withdrawn — exact-count API
  is center-of-topic, and its weakness is singleton depth, not drift.
- artifacts ground-truth: jira #7 = verbatim (post-revise text); notion
  59d7849ec9274c8da0271449d0e6831d = all sections, readable, exclusions
  documented in out_of_scope with rationale — 2-for-2 on revised PRDs
  doing the cut's bookkeeping; slack ts 1784847158.393315 = composed,
  carries exclusions + repro-risk caveat, closes with an ask. No leakage.
- wall-clock: invoke → PRD render 0:59; revise → second render 0:51;
  approve → final report 1:00.
  
---