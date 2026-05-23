# Agentic-Projects
Building agentic solutions to real world problems


# ProcureIQ — An Agentic Vendor-Evaluation System

ProcureIQ turns a messy folder of vendor RFI/RFP submissions: Excel questionnaires, PDF proposals, pricing workbooks, slide decks, into a single, defensible procurement recommendation that a sourcing lead can take into a committee meeting. It is built as a set of **Claude Code subagents** that ingest mixed-format documents, normalize them against a fixed rubric, score vendors, and render a finished PDF analysis.

It was developed as the technical core of an MBA consulting capstone for a North American beauty & personal-care retailer's indirect-procurement function, applied to a real category (managed transportation / 4PL logistics).

---

## Why this exists

Vendor evaluation in real procurement is slow and inconsistent because the inputs are heterogeneous and the judgment is hard to audit. Every vendor answers the same RFI differently, prices against the same matrix in incompatible formats, and buries compliance signals in 40-page PDFs. A human analyst spends days reconciling all of it, and the final recommendation is often hard to defend line-by-line.

ProcureIQ treats this as an **agentic pipeline** rather than a one-shot prompt. Each stage has a narrow job, a strict input contract, and an auditable output artifact, so the final go/no-go can always be traced back to a specific cell in a specific vendor's submission.

---

## Architecture

The system is designed around a **two-agent core** today, with a six-agent target architecture as the roadmap.

### Implemented agents

| Agent | Role | Output |
|---|---|---|
| `rfi-normalizer` | Takes a fixed RFI template + a folder of vendor-filled RFIs + a sourcing brief. Normalizes every vendor's answers onto the canonical question set and ranks them by fit. | A wide comparison PDF **and** a structured `vendor_data.json` |
| `proposal-analyst` | End-to-end orchestrator. Ingests the full RFP package (code of conduct, processes, price matrix, responsible-procurement letter, Q&A) plus vendor proposals, derives the rubric, delegates RFI normalization to `rfi-normalizer`, then produces the final recommendation. | A 3-section PDF: business-practice flags, normalized financials, go/no-go |

The key design choice is **delegation with a JSON contract**. `proposal-analyst` does not re-parse RFIs itself — it calls `rfi-normalizer` and consumes the `vendor_data.json` that agent emits. This keeps the financial table and the business-practice table provably consistent and means either agent can be run and audited on its own.

### Target architecture (roadmap)

The full conceptual design extends the core into a six-agent procurement workflow:

`Vendor Intelligence → Market Intel → RFI Normalization → Proposal Analysis → Negotiation Strategy → Contract Monitoring`

The two agents in this repo implement the **RFI Normalization** and **Proposal Analysis** stages — the analytical heart of the pipeline. The remaining four are specified but not yet built here.

### Document ingestion

Both agents lean on format-specific skills to read whatever vendors actually submit, rather than assuming clean inputs:

- `.xlsx` → spreadsheet parsing (RFI responses, price matrices, Q&A)
- `.pdf` → proposal text and compliance-letter extraction
- `.docx` / `.pptx` → supplementary docs and proposal decks

Missing or blank answers are recorded as an em dash (`—`) and **never inferred** — a deliberate "absence over fabrication" rule that runs through the whole system.

---

## Scoring methodology

The recommendation is produced in two stages, by design, so that price never rescues a vendor that fails a non-negotiable.

**Stage 1 — Hard-constraint cutoff.** Any vendor that fails a hard constraint (e.g. code-of-conduct alignment, responsible-procurement agreement, a mandatory certification named in the RFP) is eliminated outright, with the specific failing rule and a citation. Eliminated vendors are not scored further.

**Stage 2 — Weighted ranking** for the survivors:

```
score = 0.70 × price_score + 0.30 × green_flag_density

price_score          = (lowest_complete_total / vendor_total) × 100
green_flag_density    = (GREEN cells in soft-rule columns / soft-rule columns) × 100
```

Vendors with incomplete pricing are scored on a best-case basis and **explicitly flagged** rather than silently estimated. If the top two survivors land within 3 points, the system calls a tie and recommends further investigation instead of presenting false precision.

The category-level rubric is fully weighted and transparent. For the logistics category, for example, the weighting distributes across eleven criteria:

| # | Criterion | Weight |
|---|---|---|
| 1 | Strategic fit (industry experience) | 15 |
| 2 | Service specialization | 15 |
| 3 | Quality & ESG certifications | 15 |
| 4 | Geographic coverage | 10 |
| 5 | Financial stability | 10 |
| 6 | Technology (TMS, KPIs, API readiness) | 10 |
| 7 | Scale & capacity | 5 |
| 8 | Carrier-network flexibility | 5 |
| 9 | Operational excellence (SLAs, escalation) | 5 |
| 10 | Risk management & continuity | 5 |
| 11 | RFI response quality | 5 |

Weights are configuration, not code — the rubric is derived per category from the client's own RFP appendices, so a different procurement category produces a different (but equally auditable) weighting.

---

## Python tooling

| File | What it does |
|---|---|
| `generate_pdf.py` | Renders the vendor-comparison analysis to a polished landscape PDF using **ReportLab** — weighted-criteria tables, red/green/neutral cell shading, scoring summary, and recommendation. Emoji are mapped to colored glyphs since ReportLab can't render them. |
| `md_to_pdf.py` | A reusable Markdown → styled-PDF renderer (ReportLab). Handles headings, bold/italic, inline code, bullet lists, tables, and colored status circles. Useful well beyond this project as a general report-rendering utility. |

### Auditable intermediate artifacts

The pipeline persists its reasoning as JSON at each stage so a human can inspect (and correct) the machine's work before trusting the final PDF:

- `rubric.json` — the derived rubric: hard constraints, soft rules, and the pricing schema, each citing its source document.
- `proposal_data.json` — per-vendor extracted business-practice signals and pricing answers, with source file/page citations.
- `vendor_data.json` — the normalized RFI comparison emitted by `rfi-normalizer` and consumed by `proposal-analyst`.

This "show your work" layer is what makes the recommendation defensible: every `GREEN`/`RED` flag and every cost figure traces back to a real cell in a real submission.

---

## Repository structure

```
ProcureIQ/
├── README.md
├── .gitignore
├── agents/
│   ├── proposal-analyst.md      # end-to-end orchestrator agent
│   └── rfi-normalizer.md        # RFI comparison subagent
├── tooling/
│   ├── generate_pdf.py          # ReportLab analysis renderer
│   └── md_to_pdf.py             # Markdown → styled PDF utility
└── sample_data/                 # SYNTHETIC inputs + expected outputs
    ├── rfp_package/             # fake RFP, price matrix, Q&A
    ├── vendor_responses/        # fake filled RFIs (3–4 dummy vendors)
    └── expected_output/         # sample analysis PDF + JSON contracts
```

---

## Running it

1. Place the RFP package and vendor responses in the folders above (start with `sample_data/`).
2. Invoke `proposal-analyst` with the **procurement category** and a **sourcing brief** (the use case, hard constraints — budget/geography/compliance/timeline — and soft preferences). A vague brief produces a weak recommendation, by design.
3. The agent derives the rubric, delegates RFI normalization, scores the survivors, and writes the analysis PDF plus the JSON artifacts to the vendor-responses folder.

---


## What this demonstrates

- Decomposing an ambiguous business workflow into narrow, auditable agent roles with explicit input/output contracts.
- A defensible scoring methodology that separates disqualifiers from preferences and refuses to fabricate or over-state precision.
- Practical document-ingestion and PDF-rendering tooling that handles real-world messy inputs.
- An eye for the line between a demonstrable *system* and the confidential data it happened to run on.
