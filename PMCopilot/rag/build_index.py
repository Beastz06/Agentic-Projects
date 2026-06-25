"""Build the persistent ChromaDB collection from the issue corpus.

Human-run, load-time. Reads data/raw/github_issues.json (already on disk from
ingest.py), embeds each issue once with OpenAI, and persists to data/chroma/.
Idempotent: re-running embeds only issues not already in the collection, so it
doubles as crash-recovery for a half-populated collection.

Run from project root:  uv run python -m rag.build_index
"""
import config
import os
import json
import time
import argparse
import chromadb
import tiktoken
from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIConnectionError
from rag.constants import LABEL_DELIMITER, EMBED_ENCODING, TOKEN_BUDGET, COLLECTION_NAME

MAX_RETRIES = 5


class EmbeddingError(Exception):
    """Unrecoverable embedding failure — partial corpus must not be silent."""


def _load_corpus(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_document(issue: dict) -> str:
    """Section-labeled text for embedding quality (TITLE/BODY/COMMENTS cues)."""
    comments = "\n".join(c["body"] for c in issue.get("comments", []))
    return (
        f"TITLE: {issue['title']}\n"
        f"BODY: {issue.get('body') or ''}\n"
        f"COMMENTS: {comments}"
    )


def _build_metadata(issue: dict) -> dict:
    """All values scalar — Chroma metadata cannot hold lists or nested dicts."""
    return {
        "number": issue["number"],
        "url": issue["url"],
        "state": issue["state"],
        "labels": LABEL_DELIMITER.join(issue.get("labels", [])),
        "reactions": issue["reactions"]["total"],
    }


def _batch_by_tokens(records: list[dict]) -> list[list[dict]]:
    """Greedily pack records into batches under TOKEN_BUDGET.

    Each record is {id, document, metadata} kept together so ids/docs/metadata
    can never desync across batching. A single document exceeding the budget is
    unrecoverable (cannot fit any request) -> raise.
    """
    enc = tiktoken.get_encoding(EMBED_ENCODING)
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_tokens = 0

    for rec in records:
        n = len(enc.encode(rec["document"]))
        if n > TOKEN_BUDGET:
            raise EmbeddingError(
                f"Issue {rec['id']} alone is {n} tokens, over the "
                f"{TOKEN_BUDGET} budget — cannot embed. Investigate this issue."
            )
        if current_tokens + n > TOKEN_BUDGET:
            batches.append(current)      # close the current batch
            current, current_tokens = [], 0
        current.append(rec)
        current_tokens += n

    if current:
        batches.append(current)          # flush the final partial batch
    return batches


def _embed(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """One batched call with backoff on transient errors.

    Transient (rate limit, timeout, connection) -> retry with exponential
    backoff. Exhaustion -> raise EmbeddingError (unrecoverable, re-run to resume).
    Permanent errors (auth, bad request) are NOT caught -> they propagate and
    crash, because retrying them will never succeed.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.embeddings.create(
                model=config.EMBEDDING_MODEL, input=texts
            )
            break  # success — exit retry loop
        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            wait = 2 ** attempt  # 1, 2, 4, 8, 16
            print(f"Transient embedding error ({type(e).__name__}). "
                  f"Backing off {wait}s (attempt {attempt + 1}/{MAX_RETRIES})",
                  flush=True)
            time.sleep(wait)
    else:
        # retry loop exhausted without a successful break
        raise EmbeddingError(
            f"Embedding failed after {MAX_RETRIES} attempts (transient errors)"
        )

    return [item.embedding for item in resp.data]


def build(corpus_path: str, chroma_path: str) -> int:
    issues = _load_corpus(corpus_path)
    ids = [str(issue["number"]) for issue in issues]  # stable, source-derived

    os.makedirs(chroma_path, exist_ok=True)
    chroma = chromadb.PersistentClient(path=chroma_path)
    collection = chroma.get_or_create_collection(name=COLLECTION_NAME)

    # --- idempotency guard: embed only what's missing -------------------------
    existing = set(collection.get(ids=ids)["ids"])  # what's already on disk
    todo = [issue for issue in issues if str(issue["number"]) not in existing]

    if not todo:
        print(f"Collection already complete: {len(existing)} issues. Nothing to embed.")
        return 0

    print(f"{len(existing)} already embedded; embedding {len(todo)} new issues...")

    # weld id + document + metadata per record so batching can't desync them
    records = [
        {
            "id": str(issue["number"]),
            "document": _build_document(issue),
            "metadata": _build_metadata(issue),
        }
        for issue in todo
    ]

    batches = _batch_by_tokens(records)
    print(f"Split into {len(batches)} batch(es) under {TOKEN_BUDGET} tokens each.")

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    for i, batch in enumerate(batches, start=1):
        documents = [r["document"] for r in batch]
        embeddings = _embed(client, documents)  # backoff inside; raises on exhaustion
        collection.add(
            ids=[r["id"] for r in batch],
            embeddings=embeddings,
            documents=documents,
            metadatas=[r["metadata"] for r in batch],
        )
        print(f"  batch {i}/{len(batches)}: embedded {len(batch)} issues")

    return len(todo)


def main():
    parser = argparse.ArgumentParser(description="Embed the issue corpus into ChromaDB.")
    parser.add_argument("--corpus", default="data/raw/github_issues.json",
                        help="path to the corpus JSON")
    parser.add_argument("--chroma", default="data/chroma",
                        help="directory for the persistent ChromaDB collection")
    args = parser.parse_args()

    added = build(args.corpus, args.chroma)
    print(f"Done. Embedded {added} new issues into '{COLLECTION_NAME}' at {args.chroma}")


if __name__ == "__main__":
    main()
