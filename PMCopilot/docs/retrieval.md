# The retrieval layer

Every agent that needs context from the issue corpus calls a single retriever —
`query(text, k)` — which returns the `k` most semantically similar issues with
their metadata. The retriever is **infrastructure the agents call, not an
orchestration step**: it lives outside the graph and is invoked from inside agent
nodes, never as a pipeline stage. This keeps the corpus boundary intact —
PMCopilot reasons over an *already-collected* corpus and never gathers data
during agent execution.

The layer splits into two halves by **trigger**, which gives them two different
shapes:

- **`build_index.py`** — human-run, once, at load time. Reads the collected
  corpus from disk, embeds each issue, and persists a ChromaDB collection. A
  *script*, like ingestion.
- **`retriever.py`** — imported by agents, at runtime, many times. Embeds a query
  and returns clean records. A *library*, not a script.

Both import their shared constants (collection name, label delimiter) from one
place, so the build and query halves can never disagree on how the corpus was
stored.

---

## Design decisions

**One issue = one document.** Each issue is small enough to embed whole, so
title, body, and comments are concatenated into a single section-labeled document
(`TITLE:` / `BODY:` / `COMMENTS:`). The labels are structural cues for the
embedding model, not text to parse back — facts the agents need (labels, URL,
reaction count) live in **metadata**, which is read directly. Embedded text is
for *similarity*; metadata is for *facts read back*.

**OpenAI `text-embedding-3-small` over Voyage `voyage-3-lite`.** On a corpus this
size the quality gap is marginal and the price difference rounds to nothing.
OpenAI was already wired and validated, so choosing it avoided a new account,
key, and dependency for no meaningful gain. The model ID lives as a single
project-wide constant — the corpus and every query *must* be embedded by the same
model to share a comparable vector space.

**Idempotent, resumable build.** Issue number is the stable document ID, so
re-running the build embeds only what's missing rather than re-embedding the
whole corpus. The same guard doubles as crash recovery: if embedding fails
partway, the next run resumes from where it stopped. An unrecoverable failure (a
half-populated collection, an oversized document) raises loudly rather than
leaving a silent partial corpus.

**Token-aware batching.** OpenAI caps a single embedding request at 300k tokens;
the corpus exceeds that in one call. Rather than guess a fixed batch size from
the *average* document, the build measures tokens and packs batches under a
budget — so it survives a corpus expansion or a switch to a larger repo without
re-tuning.

---

## A note on retrieval calibration

On this corpus, raw vector distance is a weak relevance signal on its own. GitHub
issues share heavy template boilerplate (identical checklists, package-selection
tables), so *every* issue is moderately similar to every other, and distances
compress into a narrow band — a genuinely relevant result and an off-topic one
can land at nearly the same distance.

How narrow: at the `k=8` boundary, the gap between rank 8 and rank 9 measures
0.00307 for one theme and 0.00316 for another, against band widths of roughly
0.13. The meaningful signal at the cutoff is about 2.5% of the band — smaller
than the approximate index's own traversal variance, which means two identical
queries can return different eighth results.

The retriever's job is to return the nearest `k` faithfully; judging whether
those neighbors are *good enough to use* is a separate gate layered on top. The
practical implications: that gate cannot be a naive absolute-distance cutoff, and
stripping issue-template boilerplate before embedding is a candidate improvement
for sharpening the signal.
