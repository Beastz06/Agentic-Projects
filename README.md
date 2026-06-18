# Agentic-Projects

Building agentic solutions to real-world problems.

A portfolio of self-contained agentic systems. Each project lives in its own folder with its own README, sample data, and full documentation. This page is the directory -- open any project's folder for the in-depth writeup.

---

## Projects

### ProcureIQ -- Agentic Vendor-Evaluation System
**Status: Built** | [-> ProcureIQ/](./ProcureIQ)

Turns a messy folder of vendor RFI/RFP submissions -- Excel questionnaires, PDF proposals, pricing workbooks, slide decks -- into a single, defensible procurement recommendation a sourcing lead can take into a committee meeting. Built as Claude Code subagents that ingest mixed-format documents, normalize them against a derived rubric, eliminate vendors that fail hard constraints, and score the survivors. Every flag and cost figure traces back to a real cell in a real submission, so the final go/no-go is auditable line-by-line. Developed as the technical core of an MBA consulting capstone for a real logistics-sourcing category.

---

### PMCopilot -- Multi-Agent PM Assistant
**Status: In progress** -- PRD and architecture complete; build underway | [-> PMCopilot/](./PMCopilot)

A multi-agent assistant for a PM building next quarter's roadmap under a hard deadline. The PM arrives with an already-collected corpus of product issues; PMCopilot structures and reasons over it -- it does not gather the data. A LangGraph supervisor orchestrates four agents: a Discovery Researcher that turns raw issues into themed, citation-grounded findings; a PRD Drafter that produces a validated PRD with testable acceptance criteria; a Roadmap Planner that prioritizes by effort, impact, dependencies, and quarter; and a Stakeholder Summarizer that emits audience-tailored summaries in one pass. Guardrails prevent fabricating, inflating, or inventing issues, and an LLM-as-Judge eval suite scores output quality. Designed PRD-first: the product spec and architecture exist before any production code.

---

## Repository layout
Agentic-Projects/

|-- README.md          (you are here)

|-- ProcureIQ/         built: agentic vendor evaluation

+-- PMCopilot/         in progress: multi-agent PM assistant
