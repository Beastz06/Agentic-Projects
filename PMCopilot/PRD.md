# PMCopilot — Product Requirements Document

> A multi-agent assistant that turns a collected corpus of product issues into structured, prioritized, decision-ready PM artifacts: a PRD, a roadmap, and per-stakeholder summaries.

---

## Target User

A product manager building next quarter's product roadmap under a hard deadline of 4–5 days. They already have the raw signal about what's wrong with the product — but it's unstructured and scattered, and it has to become decision-ready before the deadline.

---

## Problem Statement

A PM is building next quarter's product roadmap under a hard deadline of 4–5 days. The raw signal about what's wrong with the product exists, but it's unstructured and scattered, and it has to become structured, prioritized, decision-ready artifacts (PRD, roadmap, stakeholder summaries) before the deadline.

PMCopilot does not gather the issues; it structures and reasons over the corpus of already-collected issues. Guardrails prevent it from inventing new issues, fabricating the underlying data, or overstating real issues by inflating scope or severity. From this corpus, PMCopilot generates a complete and actionable PRD covering all prominent issues, grouping issues together where they reflect the same underlying problem, with acceptance criteria that are testable and atomic. The final PRD gives the PM a structured picture of the product's issues, and PMCopilot further assists by generating a thorough, prioritized roadmap and tailored summaries for each stakeholder group.

---

## User Stories

One per agent in the pipeline.

**Discovery**
As a PM under a strict deadline, I want to transform a corpus of GitHub issues into themed findings grounded in cited issue IDs, so that the structuring work that took 2–3 days now takes minutes.

**PRD Drafter**
As a PM under a strict deadline, I want to create a validated PRD from the themed findings, so that I have a detailed action plan with minimal scope creep and clear, testable acceptance criteria.

**Roadmap**
As a PM under a strict deadline, I want to create a prioritized roadmap from the issues in the PRD, weighed on the basis of effort, impact, dependencies, and target quarter, so that I have a clear timeline of what needs to be fixed and when.

**Summarizer**
As a PM under a strict deadline, I want to create audience-tailored summaries, one per stakeholder group, from the finished artifacts, so that I get every stakeholder framing in one pass instead of manually re-writing the same content N times for N stakeholder groups.

---

## Success Metrics

Measured by an LLM-as-Judge eval suite over 10 scenarios. Each dimension is scored on a 1–5 anchor scale.

| Dimension | Definition | Target |
|---|---|---|
| **Hallucination** | No issue is fabricated. Every issue, fact, and figure in the PRD traces back to the corpus. | All 10 scenarios score 5 (mean = 5.0, zero scenarios below 5). |
| **Grounding** | No imprecision, unsupported escalation, or contradiction in the PRD relative to the corpus. | All 10 scenarios score 5 (mean = 5.0, zero scenarios below 5). |
| **Completeness** | No prominent themes missed; the majority of minor themes covered. | Mean score ≥ 4.0 across 10 scenarios. |
| **AC Quality** | Acceptance criteria are clear, atomic, and free of redundant pairs. | Mean score ≥ 4.5 across 10 scenarios. |

The asymmetry is deliberate: hallucination and grounding are zero-tolerance failure modes in a PM artifact — a fabricated issue or an inflated claim is unforgivable — so they carry a perfect-score floor. Completeness and AC quality are held to a high but non-perfect bar, reflecting that minor-theme coverage and AC polish are harder to guarantee across varied scenarios.

---

## Out of Scope

PMCopilot reasons over an already-collected corpus. It does **not**:

- **Gather or collect issues.** The PM arrives with the corpus; PMCopilot structures and reasons over it.
- **Ingest client conversations or call transcripts.** The corpus is GitHub issues. Unstructured conversational data is out of scope.
- **Scrape channels** (Slack, email, meeting notes) where pain points are originally discussed. Collection across channels remains the PM's manual responsibility.
