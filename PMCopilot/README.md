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

---

## The retrieval layer

Every agent that needs context from the issue corpus calls a single retriever — `query(text, k)` — which returns the `k` most semantically similar issues with their metadata. The retriever is **infrastructure the agents call, not an orchestration step**: it lives outside the graph and is invoked from inside agent nodes, never as a pipeline stage. This keeps the corpus boundary intact — PMCopilot reasons over an *already-collected* corpus and never gathers data during agent execution.

The layer splits into two halves by **trigger**, which gives them two different shapes:

- **`build_index.py`** — human-run, once, at load time. Reads the collected corpus from disk, embeds each issue, and persists a ChromaDB collection. A *script*, like ingestion.
- **`retriever.py`** — imported by agents, at runtime, many times. Embeds a query and returns clean records. A *library*, not a script.

Both import their shared constants (collection name, label delimiter) from one place, so the build and query halves can never disagree on how the corpus was stored.

### Design decisions

- **One issue = one document.** Each issue is small enough to embed whole, so title, body, and comments are concatenated into a single section-labeled document (`TITLE:` / `BODY:` / `COMMENTS:`). The labels are structural cues for the embedding model, not text to parse back — facts the agents need (labels, URL, reaction count) live in **metadata**, which is read directly. Embedded text is for *similarity*; metadata is for *facts read back*.

- **OpenAI `text-embedding-3-small` over Voyage `voyage-3-lite`.** On a corpus this size the quality gap is marginal and the price difference rounds to nothing. OpenAI was already wired and validated, so choosing it avoided a new account, key, and dependency for no meaningful gain. The model ID lives as a single project-wide constant — the corpus and every query *must* be embedded by the same model to share a comparable vector space.

- **Idempotent, resumable build.** Issue number is the stable document ID, so re-running the build embeds only what's missing rather than re-embedding the whole corpus. The same guard doubles as crash recovery: if embedding fails partway, the next run resumes from where it stopped. An unrecoverable failure (a half-populated collection, an oversized document) raises loudly rather than leaving a silent partial corpus.

- **Token-aware batching.** OpenAI caps a single embedding request at 300k tokens; the corpus exceeds that in one call. Rather than guess a fixed batch size from the *average* document, the build measures tokens and packs batches under a budget — so it survives a corpus expansion or a switch to a larger repo without re-tuning.

### A note on retrieval calibration

On this corpus, raw vector distance is a weak relevance signal on its own. GitHub issues share heavy template boilerplate (identical checklists, package-selection tables), so *every* issue is moderately similar to every other, and distances compress into a narrow band — a genuinely relevant result and an off-topic one can land at nearly the same distance. The retriever's job is to return the nearest `k` faithfully; judging whether those neighbors are *good enough to use* is a separate gate layered on top (see the eval and threshold work). The practical implication: that gate cannot be a naive absolute-distance cutoff, and stripping issue-template boilerplate before embedding is a candidate improvement for sharpening the signal.
