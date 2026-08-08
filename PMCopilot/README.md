# PMCopilot

**A multi-agent system that turns a collected corpus of product issues into a PRD, a prioritized roadmap, and per-stakeholder summaries — with a human approval gate in the middle.**

LangGraph · Anthropic API · ChromaDB · MCP · Pydantic v2 · Streamlit

<!-- DEMO GIF — backfill on recording day -->
<!-- LOOM LINK — backfill on recording day -->

---

## Results

### Acceptance-criterion quality: 1.40 → 4.33

Output is scored by an LLM-as-Judge on four dimensions, 1–5. Opus judges Sonnet's
output, so the judge's blind spots don't correlate with the drafter's.

| dimension | v1 | v2a | v2b | target | |
|---|---|---|---|---|---|
| **ac_quality** | 1.40 | 2.67 | **4.33** | ≥ 4.5 | miss |
| completeness | 4.33 | 4.33 | 4.11 | ≥ 4.0 | meets |
| hallucination | 4.00 | 4.00 | 4.00 | all 5 | miss |
| grounding | 4.00 | 4.00 | 3.89 | all 5 | miss |

<sub>n=9 scenarios, same nine across runs. Measured noise floor ±0.2.</sub>

v1 failed badly: every PRD carried three or more defective acceptance criteria.
Two revisions to the drafter's `SYSTEM_PROMPT` — no schema, model, or retrieval
change — moved it to 4.33. What moved it was **not clearer instruction**. Each
fix added one worked bad → good example beside a rule already stated in prose,
first for atomicity, then for vagueness. Each collapsed the defect it targeted:
non-atomic 5 → 1, vague 8 → 2, total findings 13 → 3.

`PRD.md` commits to 4.5. **This misses by 0.17 — inside the noise floor.** A
single run can't distinguish it from a pass. Recorded as a miss; the bar was not
moved. Nothing untargeted shifted by more than the noise floor, which is the
evidence the fixes were specific.

### A schema defect was costing 27% of every run's input tokens

Instrumenting the pipeline end-to-end surfaced what the eval suite couldn't see.
The drafter's forced tool call returned the PRD nested one level deep. Validation
read the required fields as missing, and the repair loop burned retries
recovering *shape* rather than fixing *content*.

| | before | after |
|---|---|---|
| input tokens / run | 58,649 | **42,740** |
| drafter tokens | 20,487 | **4,475** |
| repair fires (10-theme capture) | 13 | **0** |
| scenarios captured | 9 of 10 | **10 of 10** |

The obvious cause was the JSON Schema's own `title`, which named the key the
model was reaching for. **That hypothesis was wrong** — with the title removed,
the model still nested under the same key. What shipped is a guarded unwrap that
emits its own telemetry event, so the defect is corrected without a retry *and*
stays visible in the transcript instead of vanishing into a clean number. That
instrumentation is what caught the bad hypothesis; a silent fix would have
produced identical numbers and let the wrong explanation ship.

Current evidence points at the tool's *name*: first-pass drafts nest every time,
while a revision pass — which carries a correctly-shaped PRD in context — does
not. n=1 on the revise side, recorded as an open question, not a finding.

### Cost, measured

| segment | tokens in | tokens out | calls |
|---|---|---|---|
| discovery | 24,463 | 598 | 1 |
| drafting | 4,475 | 2,264 | 1 |
| planning | 3,901 | 362 | 2 |
| summarizing (3 audiences + Slack) | 9,901 | 3,926 | 4 |

<sub>Clean run, n=2, spread ±0.39%. A revision adds 11.0% to input. Planner
measured at one PRD — the floor, not the operating point.</sub>

Discovery is 57% of a clean run's input in a single call.

---

## The problem

A PM builds next quarter's roadmap in 4–5 days. The raw signal already exists but
is unstructured and scattered. PMCopilot **does not gather** issues — the PM
arrives with the corpus. It structures and reasons over it, with guardrails
against inventing or inflating what isn't there.

Full framing in [PRD.md](./PRD.md).

| agent | takes | produces |
|---|---|---|
| **Discovery Researcher** | raw issue corpus | themed findings, each grounded in cited issue IDs |
| **PRD Drafter** | themed findings | validated PRD with testable, atomic acceptance criteria |
| **Roadmap Planner** | approved PRDs | priority scores, dependencies, target quarters |
| **Stakeholder Summarizer** | approved PRD | audience-tailored digests, one per stakeholder group |

---

## Architecture

A LangGraph supervisor orchestrates the four agents. Data flows through the
agents; the supervisor routes *control* only. Discovery calls an MCP server as an
external tool.

![Architecture](./docs/architecture.png)

Control is hub-and-spoke: every agent returns to the supervisor, which owns all
routing plus START and END. After the drafter runs, a **human-in-the-loop gate**
lets the PM approve or request a revision in free text; the revise loop is
bounded.

![State machine](./docs/state-machine.png)

---

## Design notes

Longer write-ups, kept out of this page:

- **[Retrieval layer](./docs/retrieval.md)** — why one issue is one document, why
  the index build is a script and the query path is a library, and why raw vector
  distance is a weak relevance signal on a corpus of GitHub issues that all share
  template boilerplate.
- **[PRD.md](./PRD.md)** — the product spec this system was built against,
  including the success-metric targets the Results section is scored on.
- **[Eval suite](./evals/)** — fixtures, judge prompt, and per-run results. Every
  number above is reproducible from a committed fixture.

---

## What I'd do next

- **Acceptance-criterion ceiling.** Half the corpus now hits `max_length=8`. The
  earlier decision not to raise it was measured on output drafted under repair
  pressure, which appears to suppress criterion counts. Open again.
- **Discovery cost.** One call carries 57% of a run's input. Nothing has tested
  whether the full retrieved set is load-bearing.
- **Planner at scale.** Every measurement so far plans a single PRD. Scoring
  differentiation, dependency edges, and quarter spreading are unexercised.
- **Grounding and hallucination.** Both sit at 4.0 against a zero-tolerance bar
  and have not moved across three runs. The prompt's worked example demonstrates
  confident invented numerics — a plausible contributor, deliberately not changed
  while acceptance criteria were the variable under test.
