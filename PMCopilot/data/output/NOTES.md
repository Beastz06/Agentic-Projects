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

---

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

---

## Zero-target metrics (all three themes)
Success metrics split into two kinds: measurable-by-us (Pydantic warning count,
xfail count, 100% parallel-call attribution in the test harness — deterministic,
runnable) and world-dependent ("0 open crash reports within a release cycle" —
depends on users filing issues, which we do not control). The latter are wishful
as written; absence of reports is not proof of a fix.

---

## Topic 3 decision: no prompt revision
Three distinct defect CLASSES, each appearing exactly once: prose miscount
(auth), Discovery scope-filter (streaming), code attribution-granularity
(tool_calling). None is an n>=2 pattern. Per parked-items discipline, all three
are logged here and will trigger a fix only on recurrence in future themes.
Two of the three are not even prompt-fixable (one is code logic, one is
borderline-promptable but premature on n=1).

---

## Prediction scorecard
- Pain-point counts: predicted 4/8 (streaming/tool_calling), actual 6/7. Both
  misses in the direction of "clustering granularity does not track title-hit
  volume linearly" — a corrected mental model going forward.
- Repair loop: predicted "won't fire" both themes — correct, 2/2. Grounding
  design absorbed two token-dense new corpus regions without a single retry.
  
---

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

---

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

---

## C5 Stakeholder Summarizer — key_claims defect chain

_Baseline: Sonnet 5, agents/summarizer.py. Input held constant against the
persisted roadmap.json + the three canonical PRDs. Fixtures in sonnet5_draws/
named by provenance stage (_prefix_baseline / _prefix_gate / _promptfix_only /
run1-2 unsuffixed / _v1_rationale_fabrication)._

### Three stacked defects, each unmasked by fixing the one above it
A single symptom (eng digest produced 0 key_claims while being the most
claim-dense of the three; gradient 12/6/0 customer/exec/eng) turned out to be
THREE independent defects in series. Each fix exposed the next. The lesson is
the shape, not any one defect: **a symptom stable across runs can still be
multi-causal; fixing the top layer and re-running is how the next layer becomes
visible.**

1. **Authorship gate (prompt-layer).** The model self-indexes by PERCEIVED
   AUTHORSHIP: near-verbatim relay of the input (eng) does not feel like "claims
   I am making," so it indexed nothing; heavy translation (customer) feels
   authored, so it indexed everything. Transformation distance drove the 12/6/0
   gradient. Load-bearing factual claim ≠ numeric claim — customer's 12 were all
   qualitative. Fix: prompt text stating a claim counts whether restated verbatim
   or translated ("restating a fact from the input is still making that claim").

2. **Freeloading schema default (schema-layer) — the real root cause of eng=0.**
   `key_claims: list[Claim] = Field(default_factory=list)` EXCLUDED the field from
   the JSON-Schema `required` array (Pydantic drops any defaulted field from
   `required`). The tool contract therefore advertised key_claims as OMISSIBLE.
   Per the banked C3 lesson read in reverse — SCHEMA OVERRIDES PROSE — the "you
   must index" prose lost to the "optional" schema. Proof: the prompt-only fix
   (stage _promptfix_only) produced ZERO behavioral delta across 3 calls. A
   prompt fix with no behavioral delta means the defect is not at the prompt
   layer. Worse: the default also LAUNDERED truncation — an omitted field became
   a clean `[]`, so our own code could not distinguish "model said nothing" from
   "model said empty." Fix: remove the default (field becomes required-present);
   omission now fails validation → repair loop. Same freeloading default was on
   `grounded_in` — fixed too. **General: a defaulted Pydantic field is silently
   optional in the tool schema; if the model must fill it, no default.**

3. **Token budget (generation-layer).** With presence forced AND relay licensed,
   a COMPLIANT eng digest (dense body + 15-20 technical claims) overran
   max_tokens=2000. The API returns partial tool input on a max_tokens cut; the
   unterminated key_claims array drops whole → dict arrives missing exactly the
   last field, deterministically, 3/3. The repair loop was retrying a BUDGET
   problem as a COMPLIANCE problem (re-running into the same ceiling) because
   nothing read `response.stop_reason`. Fix: MAX_TOKENS=4000 (calibrated from
   evidence) + detect stop_reason=="max_tokens" as a DISTINCT, non-retried
   failure that names itself. **General: a repair loop that ignores stop_reason
   will burn its full retry budget on any truncation. Detect budget cuts before
   validation; do not feed them back.**

### Layering blind spot: the judge cannot catch unindexed prose
Anti-hallucination layering assigned invented content to prompt + judge. But the
C9 judge verifies INDEXED claims against sources — a fabrication living in
unindexed body prose is invisible to it. Surfaced concretely below.

### Qualitative fabrication via the tone channel (exec)
Exec fabricated a CAUSAL claim with no numbers: "sequenced after streaming and
auth because it depends on a stable foundation" — but roadmap depends_on is []
for all three (Q2 is pure budget packing). Same digest's own key_claims stated
the truth ("no dependencies"): **the body contradicted its own index.**
Reproduced 2/2 across prompt versions (stage _v1_rationale_fabrication). Cause:
the exec tone block demands why-framing ("what ships first and why"); when the
input has a sequencing with no stated why, the model manufactures one. **The
tone instruction created the fabrication pressure — a channel never audited
because we audited schema and the numbers-rule, not the tone blocks.** Fix: a
grounding-discipline line forbidding invented reasons/causes/rationales,
explicitly overriding the tone block's why-demand ("absence of a stated
rationale is information; fabricating one destroys it"). Post-fix, the model,
denied a fake reason, surfaced the PRDs' REAL epistemics instead (thin evidence
base / one-or-two-report frequency) — the fix redirected rather than silenced.
**General: any tone instruction that demands a rhetorical move (a "why", a
benefit, a stakes-frame) is a fabrication channel when the input lacks the
material for that move. Audit tone blocks as fabrication surfaces, not just
schema and explicit content rules.**

### Provenance / fill-party (bank alongside evidence_issue_ids and PRD.theme)
grounded_in has the SAME SHAPE as C4's code-filled evidence_issue_ids (a list of
source refs) but is MODEL-filled. **Fill-party is set by who holds the
provenance, not by field shape:** retrieval provenance lives in code (code
stamps issue IDs); authorship provenance — which theme motivated the sentence —
lives only in the model. audience is the third instance of the code-stamp idiom
(caller holds it). Grounding is THEME-level, not artifact-level: a real number
is real whichever artifact (PRD or roadmap item) holds it, so a PRD-vs-roadmap
source_type discriminator was cut as over-engineering. PARKED: this cannot
express PRD-vs-roadmap-item misattribution of a real number — acceptable while
the guardrail is invented-number detection.

### Count behavior (feeds C9 multi-sample eval design)
Post-fix key_claims counts: eng 17/17 (converged — index tracks the actual claim
population once the gate is open), exec 9→11 (variance band), customer 13→15.
Sidecar carries FULL jargon (ToolNode, mTLS, SSRF) even in the customer digest
whose prose is plain — emergent and correct: the sidecar is machine-facing (judge
verification), tone governs reader-facing fields only. Cross-theme claims
(grounded in all three themes for roadmap-level facts) validated cleanly; the
membership check handled multi-theme grounding though it was never explicitly
tested for it.

### Parked items added this session
- Backport stop_reason detection to the C3/C4 repair loops (same latent blindness).
- Tone-block fabrication-surface audit as a general pass on any why/benefit/
  stakes-demanding tone instruction (recurrence-gated beyond exec n=2).
- Commit-message convention drift (C4 `feat:` vs C5 `C5:`) — pick one going forward.

---

## C7 MCP Server: Jira tools + orchestrator integration

**Deterministic filing over model-driven (deliberate).** The post-approval Jira
node maps issue fields from the approved PRD in code (`title` from theme, `body`
from problem_statement verbatim); no model composes the arguments. Rationale:
the human gate ratifies exact wording, so model rephrasing after the gate is
pure fabrication surface with no remaining judgment to exercise. The MCP
protocol boundary is unchanged either way (real stdio subprocess, real
schema-validated call) — only argument authorship is code-side. Model-driven
composition is additive later if wanted; the Slack digest post (Day 27) is the
better home for it since digests are already model-authored prose.

**Approval now means tracked.** STEP_APPROVED routes through the jira node
unconditionally — there is no approve-without-filing path. Corollary: a filing
failure is a broken invariant, not a cosmetic gap, so jira_node fails the run
(STEP_ERROR → END) rather than degrading to planner.

**Side-effect asymmetry in external tool calls.** A client-side failure after
the server writes (observed live: a response-parse bug) halts the run *after*
the issue exists in Jira. "Run failed" ≠ "no side effects happened." Any retry
or resume logic added later must account for possibly-existing artifacts.

**Checkpointed invoke input is mutation, not initialization.** Seeding
`prds: []` in a demo script silently wiped the restored PRD on a stale thread
(last-write-wins channel), while `digests: []` was harmless (reducer identity)
and `roadmap` survived by absence. Rule: on persistent threads, pass only the
keys you mean to write. Demo script now derives a fresh thread_id per run —
the pattern C8's Streamlit layer inherits.

---

## Integration Checkpoint — Full-System Runs

**Result: 5/5 full success, after a blocking defect found and fixed on run 1.**

Five end-to-end runs against the 200-issue langchain corpus with representative
topic sampling (topics a working PM would plausibly bring to this corpus, not
engineered for difficulty). Gate: approve-only on runs 2–4; revise-then-approve
on runs 1 and 5 (dense vs. thin evidence, controlled comparison). All artifacts
content-ground-truthed on every run — Jira body verbatim, Notion page fully
rendered, Slack post composed and caveat-carrying. Zero degrade-path
activations across 15 MCP tool calls.

**Blocking defect (run 1).** The roadmap planner's dependency-detection tool
built its JSON Schema with PRD theme names as property keys. Any multi-word
theme produces a hard API 400 (property keys are charset-restricted). Every
prior run in the project's history used a single-word topic, so the bug had
never fired; all five of today's topics would have failed identically. Fixed by
restructuring the tool schema so themes are values in an array, not keys —
completeness and uniqueness checks moved from schema enforcement into the
validator as repairable defects. Principle: free text must never be a JSON
Schema property key.

**Failure modes characterized.** All self-healed; none reached the gate.

| Component | Decision | Basis |
|---|---|---|
| C8 Streamlit (D29–30) | **GO** | Latencies viable for the staged-status UI Day 29 specifies: ~1:00 invoke→first PRD, ~0:51/revise, ~1:00 post-approve→final. Gate protocol survived 7 transactions across 5 threads, zero misinterpretations; checkpoint-resume worked every thread. Design requirement discovered: the UI must render retry states, not only success states. |
| C9 eval harness (D31–32) | **GO** — failure-mode measurement first, retrieval threshold second | Three defect modes at rates visible only across repeated runs (above). All self-heal, so this is a characterization problem, not a reliability one — which is what a harness is for. Retrieval demoted: today produced behavioral adequacy, no new distance-score evidence; the ~1.2-band problem is unchanged. |
| Draft PR to MCP servers repo | **GO, deferred to C10** | Quality condition met: 15 tool calls, zero degrades, zero transport failures. Deferred because the ask was a quality decision, not a same-day ship. Scope it implies: init-on-import for all three stores (elevates the carried `init_db()` / `init_store()` / `init_log()` parked item — a stranger cloning hits FileNotFoundError on first write), configurable storage paths, install/config README with the Desktop JSON block, one-server-vs-three packaging decision. |

**Go/no-go.**

| Component | Decision | Basis |
|---|---|---|
| C8 Streamlit (D29–30) | **GO** | Latencies viable for the staged-status UI Day 29 specifies: ~1:00 invoke→first PRD, ~0:51/revise, ~1:00 post-approve→final. Gate protocol survived 7 transactions across 5 threads, zero misinterpretations; checkpoint-resume worked every thread. Design requirement discovered: the UI must render retry states, not only success states. |
| C9 eval harness (D31–32) | **GO** — failure-mode measurement first, retrieval threshold second | Three defect modes at rates visible only across repeated runs (above). All self-heal, so this is a characterization problem, not a reliability one — which is what a harness is for. Retrieval demoted: today produced behavioral adequacy, no new distance-score evidence; the ~1.2-band problem is unchanged. |
| Draft PR to MCP servers repo | **GO, deferred to C10** | Quality condition met: 15 tool calls, zero degrades, zero transport failures. Deferred because the ask was a quality decision, not a same-day ship. Scope it implies: init-on-import for all three stores (elevates the carried `init_db()`/`init_store()`/`init_log()` parked item — a stranger cloning hits FileNotFoundError on first write), configurable storage paths, install/config README with the Desktop JSON block, one-server-vs-three packaging decision. |

Per-run records, predictions, and artifact checks: [`docs/integration_run.md`](../../docs/integration_run.md)

---

## C8 UI Runs — Day 29

Two runs through the Streamlit app. Four drafter fires, one full
revise-then-approve pipeline (zero errors, zero degrades, all artifacts
written). Recorded because the fires exposed a dimension the integration
checkpoint never measured.

**Retry depth is a measurement gap, not a behavioral change.** Three of four
fires consumed the full `MAX_RETRIES = 2` budget and succeeded on attempt 3 —
one failure short of `STEP_ERROR -> END`. Day 28 banked "self-heals every
time" but measured fire *rate* only; depth was never recorded. One fire also
showed **partial repair** (3 validation errors -> 1), which falsifies the
Day 20 premise that a failed repair means the model can't satisfy the
contract.

**C9 consequence:** the harness must aggregate `pmc_attempt` as a
distribution, not a count. Fire rate alone would have shown four healthy
self-heals and hidden three near-exhaustions. The field already carries it.

**Risk-collapse now 4-for-4, trigger refined.** Fired on a dense topic — the
model wrote a thin-evidence caveat anyway, so the trigger is the caveat, not
evidence density. `Severity -> schemas/common.py` is the best-evidenced open
fix in the ledger.

**New specimen (n=1):** top-level `target_user` omission with no `{'prd': ...}`
envelope — not wrapper-nesting, not in the Day 28 set. Logged, no action.

Per-fire records: [`docs/ui_run.md`](../../docs/ui_run.md)

---