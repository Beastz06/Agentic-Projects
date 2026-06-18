# PMCopilot

A multi-agent assistant that turns a collected corpus of product issues into structured, prioritized, decision-ready PM artifacts -- a PRD, a roadmap, and per-stakeholder summaries.

---

## The problem

A PM is building next quarter's roadmap under a hard deadline of 4-5 days. The raw signal about what's wrong with the product already exists, but it's unstructured and scattered, and it has to become decision-ready before the deadline. PMCopilot **does not gather** the issues -- the PM arrives with the corpus already collected. PMCopilot structures and reasons over it, with guardrails against inventing, fabricating, or inflating issues.

Full detail in [PRD.md](./PRD.md).

---

## Architecture

A LangGraph supervisor orchestrates a four-agent pipeline. Data flows left-to-right through the agents; the supervisor routes *control* (it decides what runs next, it does not pass data); and the Discovery agent calls an MCP server as an external tool.

![Architecture](./docs/architecture.png)

- **Solid** lines = data flow
- **Dashed** lines = control flow (supervisor to agents)
- **Dotted** line = client-server call (Discovery to/from MCP server)

---

## State machine

Control follows a hub-and-spoke pattern: every agent returns to the supervisor, which owns all routing decisions plus START and END. After the PRD Drafter runs, a **human-in-the-loop gate** lets the PM approve or request a revision; the revise loop is bounded so it can't run unbounded.

![State machine](./docs/state-machine.png)

- **Solid** = unconditional routing
- **Dashed** = the conditional branch after PM review (approve OR count >= N -> proceed; revise AND count < N -> back to PRD Drafter)

---

## The four agents

- **Discovery Researcher** -- turns the raw issue corpus into themed findings, each grounded in cited issue IDs.
- **PRD Drafter** -- produces a validated PRD with testable, atomic acceptance criteria from the themed findings.
- **Roadmap Planner** -- prioritizes the PRD's issues by effort, impact, dependencies, and target quarter.
- **Stakeholder Summarizer** -- emits audience-tailored summaries, one per stakeholder group, in a single pass.

---

## How quality is measured

Output is scored by an LLM-as-Judge eval suite across four dimensions -- Hallucination, Grounding, Completeness, and AC Quality -- on a 1-5 anchor scale over a set of test scenarios. Hallucination and Grounding are held to a zero-tolerance bar; Completeness and AC Quality to a high but non-perfect bar. Targets and rationale are in [PRD.md](./PRD.md#success-metrics).

---

## Tech Stack

LangGraph (orchestration) | Anthropic API (agents) | ChromaDB (vector store / retrieval) | MCP (external tools) | Pydantic v2 (schemas & validation) | Streamlit (UI)