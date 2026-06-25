"""Query helper over the persistent ChromaDB issue collection.

Imported infrastructure — agents call query(text, k=5) at runtime. Translates
Chroma's nested response into a flat list of records so agents never depend on
the database's response shape (swap Chroma later, only this file changes).

Lazy: the client/collection open on first query and are cached for reuse, so an
agent calling query() repeatedly pays the open cost once. Importing this module
does NOT require the collection to exist yet — only querying does.
"""
import config
import chromadb
from openai import OpenAI
from rag.constants import COLLECTION_NAME, LABEL_DELIMITER

DEFAULT_CHROMA_PATH = "data/chroma"

_collection = None  # module-level cache, populated on first query


def _get_collection(chroma_path: str = DEFAULT_CHROMA_PATH):
    """Open and cache the collection. Raises if the index was never built."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=chroma_path)
        # get_collection (NOT get_or_create): raise loudly if the index is
        # missing, rather than silently creating an empty one and returning
        # zero results — an unbuilt index is unrecoverable at query time.
        _collection = client.get_collection(name=COLLECTION_NAME)
    return _collection


def _embed_query(text: str) -> list[float]:
    """Embed the query with the SAME model used to build the corpus.

    Query and corpus vectors must share an embedding space to be comparable;
    config.EMBEDDING_MODEL is the single source of truth for that symmetry.
    One short string — no batching or backoff ceremony needed.
    """
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=[text])
    return resp.data[0].embedding


def query(text: str, k: int = 5) -> list[dict]:
    """Return the k issues most similar to `text` as a flat list of records.

    Each record: {number, url, state, labels (list), reactions, document, distance}.
    """
    collection = _get_collection()
    query_vec = _embed_query(text)

    res = collection.query(query_embeddings=[query_vec], n_results=k)

    # Chroma returns parallel lists nested one level deep (one row per query).
    # We sent one query, so everything is at index [0].
    ids = res["ids"][0]
    documents = res["documents"][0]
    metadatas = res["metadatas"][0]
    distances = res["distances"][0]

    records = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        labels_str = meta.get("labels", "")
        records.append({
            "number": meta.get("number"),
            "url": meta.get("url"),
            "state": meta.get("state"),
            "labels": labels_str.split(LABEL_DELIMITER) if labels_str else [],
            "reactions": meta.get("reactions"),
            "document": doc,
            "distance": dist,
        })
    return records
