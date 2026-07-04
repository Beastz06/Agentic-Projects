# Vertical Slice Checkpoint — Observed Failure Modes

Three themes run end-to-end (Discovery → PRD Drafter): authentication (Day 20
specimen), streaming, tool_calling. Each PRD reviewed by hand against three
axes: (a) problem-statement specificity, (b) AC testability, (c) citation
relevance (provenance is code-guaranteed; relevance is not).

## Cross-cutting: provenance held, relevance is the real test
Across all three PRDs, every cited issue ID traced to a real in-theme corpus
issue — zero fabricated IDs. The code-attaches-IDs architecture (model writes
indices only; code overwrites evidence_issue_ids from the verified pain-point
pool) held on all three themes. The repair loop never fired across any run.
Relevance — does the cited issue actually support the story's claim — is where
the defects live, and it is not something provenance guarantees.

## Per-theme findings

### authentication
- Problem statement says "three categories of failure" then lists four —
  structure passes Pydantic, a judge dings the prose. (Drafter prose discipline.)
- Story 5 is cross-cutting (merged indices) — evidence supports the synthesized
  story, verified.
- Several success metrics are "0 new issues" targets — see zero-target note below.

### streaming (6 pain points; predicted 4 — corpus split finer, not coarser)
- Problem statement structure correct: six defects claimed, six delivered. The
  auth three-vs-four miscount did NOT recur.
- All six citations provenance-clean and relevance-valid. Story 2 initially
  looked like an overclaim (one citation, two claims) but the cited issue
  (35436) itself reports both bugs — grounded. Lesson: a citation-count/claim-
  count mismatch is a prompt to check the source, not a verdict.
- FLAW — Story 6 persona/target-user conflict: target_user is "LangChain
  users/integration developers," but Story 6's persona is "a LangChain
  contributor maintaining the test suite" (issue 36866, a test-assertion bug).
  Discovery clustered by theme and swept a maintenance/internal issue into a
  user-facing PRD. Scope-filtering gap at the Discovery stage.

### tool_calling (7 pain points; predicted 8)
- Problem statement + ACs clean. AC #8 (budget signaled before planning) is
  correctly tied to pain point 6 — apparent disconnect was a non-linear
  story→AC mapping artifact (pain point 1 split into two stories/ACs), not a defect.
- Issue 35836 correctly dual-cited by Story 3 (Gemini rejects replayed tool-call
  history) and Story 6 (missing injection API) — the single issue genuinely
  raises both threads.
- FLAW — Stories 1/2 citation cross-contamination: pain point 1 fissioned into
  two narrower stories (parser crash 36679; streaming empty-args 35514), but
  the code copied the pain point's FULL pooled ID list onto both child stories.
  Each story now carries one on-target and one off-target citation. Provenance
  intact (both IDs trace to PP1); relevance broke at the split. This is a CODE
  attribution-granularity gap (how IDs propagate when one pain point yields
  multiple stories), not a prompt issue.

## Zero-target metrics (all three themes)
Success metrics split into two kinds: measurable-by-us (Pydantic warning count,
xfail count, 100% parallel-call attribution in the test harness — deterministic,
runnable) and world-dependent ("0 open crash reports within a release cycle" —
depends on users filing issues, which we do not control). The latter are wishful
as written; absence of reports is not proof of a fix.

## Topic 3 decision: no prompt revision
Three distinct defect CLASSES, each appearing exactly once: prose miscount
(auth), Discovery scope-filter (streaming), code attribution-granularity
(tool_calling). None is an n>=2 pattern. Per parked-items discipline, all three
are logged here and will trigger a fix only on recurrence in future themes.
Two of the three are not even prompt-fixable (one is code logic, one is
borderline-promptable but premature on n=1).

## Prediction scorecard
- Pain-point counts: predicted 4/8 (streaming/tool_calling), actual 6/7. Both
  misses in the direction of "clustering granularity does not track title-hit
  volume linearly" — a corrected mental model going forward.
- Repair loop: predicted "won't fire" both themes — correct, 2/2. Grounding
  design absorbed two token-dense new corpus regions without a single retry.
  
## Sonnet 5 regeneration — auth theme

_Baseline note: the checkpoint sections above describe the reviewed 4.6 output.
Everything in this section is Sonnet 5, generated during the model regeneration._

**Counts stable across 3 draws: 4 pain points / 4 stories / 6 ACs (all three).**
Contrast with the streaming theme, which varied on every axis (6/7/6 points,
6/5/6 stories, 7/8/8 ACs). Auth's four defects (mTLS/custom-client, httpx
inconsistency across Azure/base OpenAI, MCP header forwarding, SSRF LANGCHAIN_ENV
bypass) are cleanly separable, so clustering lands identically run-to-run.
Streaming's clusters are borderline (issue-template boilerplate compresses
embedding space on this corpus).
HYPOTHESIS (pending third theme): Sonnet 5 structural variance tracks cluster
separability of the theme, not a global model constant.
[SUPERSEDED — see tool_calling section: count-variance and fission-variance are
independent axes; the single-axis "cluster separability" framing was too coarse.]

**Prose-consistency defect (problem_statement miscounts its own enumeration)
CLEARED on Sonnet 5, 3/3.** All three auth draws enumerate four defects in
problem_statement matching 4 pain points — the 4.6 auth "says three, lists four"
miscount did not recur. Contrast the Discovery scope-filter defect logged in the
4.6 streaming section (a maintainer-scoped test-suite issue swept into a
developer-facing PRD): that one REPRODUCED on Sonnet 5, confirming it is
model-invariant.
HYPOTHESIS (pending third theme): defect *location* predicts model-swap
sensitivity — upstream/data defects (Discovery scope-filtering) are model-
invariant; downstream/drafting defects (prose discipline) are model-responsive.

**`prd`-envelope nesting failure fired on auth draw 3.**
Previously observed only on the streaming theme. Confirms it is stochastic and
theme-independent, not streaming-specific. Repair loop caught it, repaired
first-try, saved a valid PRD (validates against PRD schema). Reinforces prior
call: this quirk belongs in the repair loop, not an upstream extraction fix.

**Repair-provenance / canonical selection.**
auth run 3 is a POST-REPAIR sample (attempt-1 nesting failure → repair loop →
valid). Runs 1 and 2 are clean-first-pass. Canonical = run 1 (clean-first-pass —
a principled choice, unlike the streaming theme where all three were clean and
selection was arbitrary). Run 3 kept as an eval fixture WITH this repair flag:
for raw-output-distribution characterization, a repaired sample is
post-intervention, not raw — it must not be treated as an equivalent raw sample.

## Sonnet 5 regeneration — tool_calling theme

**Counts variable (7 / 8 / 8 across three draws) but story-mapping 1:1 every
draw.** No pain-point index appeared in more than one story on any draw. So
tool_calling is count-variable but structurally stable — distinct from streaming
(variable on every axis) and auth (stable on every axis).

**4.6 citation cross-contamination did NOT reproduce, 3/3 — but the code flaw is
untouched, not fixed.** The 4.6 defect required a specific structure: one pain
point pooling multiple issue IDs, then fissioning into multiple stories, with
code copying the full pooled ID list onto each child. Across all three Sonnet 5
draws that structure never occurred. Sonnet 5 handled the 4.6 trigger IDs
(36679 parser-crash, 35514 streaming-empty-args) two ways, neither triggering:
draw 1 kept both IDs on ONE story (one pain point, no split); draws 2 and 3
SEPARATED them into two distinct pain points upstream (one clean ID each).
The code attribution-granularity flaw remains present and latent — it is gated
by a fission structure Sonnet 5 did not produce (0 of 9 draws across all three
themes fissioned a pain point into multiple stories).

**Parked-item status (code attribution-granularity fix): STAYS PARKED, rationale
sharpened.** Not "unobserved" — the trigger structure (pooled-and-fissioned pain
point) was not generated by Sonnet 5 across 9 draws. The flaw is therefore
UNTESTED against a live trigger on Sonnet 5. To exercise it, a synthetic fixture
that forces the pooled-and-fissioned structure would be needed (candidate work
for the eval pipeline) — do not unpark on model change alone.

**Refined hypothesis (supersedes the cluster-separability hypothesis in the
streaming and auth sections):** pain-point COUNT variance and story-DECOMPOSITION
(fission) variance are INDEPENDENT axes of Sonnet 5 non-determinism, not one
phenomenon. Evidence across three themes: streaming varied both; tool_calling
varied count only (7/8/8, mapping 1:1); auth varied neither (4/4/6 × 3). The
code attribution-granularity flaw is gated specifically by the fission axis,
which stayed inert across all nine draws.

**Canonical selection.** All three draws clean-first-pass (repair loop fired on
none). Selection is arbitrary (as with streaming), not principled-by-repair (as
with auth). Canonical = run 1 by convention — the 7-point variant; the count
difference is NOT a quality ranking.
