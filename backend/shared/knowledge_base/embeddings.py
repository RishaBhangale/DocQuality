"""
Embedding and chunking service for Knowledge Base.

Uses ChromaDB's built-in all-MiniLM-L6-v2 sentence-transformer model
for local embeddings (no external API needed). Designed to be swapped
to Azure OpenAI embeddings when available.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# ── Chunking ─────────────────────────────────────────────────────────────────

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split text into overlapping character chunks.

    Returns a list of dicts with keys: text, start, end, index.
    """
    if not text or not text.strip():
        return []

    chunk_size = max(100, chunk_size)
    overlap = max(0, min(overlap, chunk_size - 1))

    chunks: list[dict] = []
    start = 0
    n = len(text)
    idx = 0

    while start < n:
        end = min(start + chunk_size, n)
        chunk_text_slice = text[start:end].strip()

        if chunk_text_slice:
            chunks.append({
                "text": chunk_text_slice,
                "start": start,
                "end": end,
                "index": idx,
            })
            idx += 1

        if end >= n:
            break
        start = end - overlap

    return chunks


# ── ChromaDB Client ──────────────────────────────────────────────────────────

_CHROMA_DIR: Optional[str] = None
_client: Optional[chromadb.ClientAPI] = None


def _get_chroma_dir() -> str:
    """Get or create the ChromaDB persistence directory."""
    global _CHROMA_DIR
    if _CHROMA_DIR is None:
        base = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base"
        base.mkdir(parents=True, exist_ok=True)
        _CHROMA_DIR = str(base)
    return _CHROMA_DIR


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create the persistent ChromaDB client."""
    global _client
    if _client is None:
        persist_dir = _get_chroma_dir()
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB client initialized at: %s", persist_dir)
    return _client


def get_collection(workspace: str) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection for the given workspace.

    Each workspace (compliance / banking) has its own isolated collection.
    Uses ChromaDB's default embedding function (all-MiniLM-L6-v2).
    """
    client = get_chroma_client()
    collection_name = f"kb_{workspace}"
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"workspace": workspace, "hnsw:space": "cosine"},
    )
    logger.debug("Collection '%s' ready: %d documents", collection_name, collection.count())
    return collection


# ── Vector Operations ────────────────────────────────────────────────────────

def add_chunks_to_collection(
    workspace: str,
    doc_id: str,
    filename: str,
    chunks: list[dict],
) -> int:
    """
    Embed and store text chunks in the workspace's ChromaDB collection.

    Returns the number of chunks added.
    """
    if not chunks:
        return 0

    collection = get_collection(workspace)

    ids = [f"{doc_id}_chunk_{c['index']}" for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": c["index"],
            "start_char": c["start"],
            "end_char": c["end"],
        }
        for c in chunks
    ]

    # ChromaDB handles embedding automatically via default embedding function
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info(
        "Added %d chunks for '%s' to collection 'kb_%s'",
        len(chunks), filename, workspace,
    )
    return len(chunks)


def remove_chunks_for_document(workspace: str, doc_id: str) -> int:
    """Remove all chunks belonging to a specific document from ChromaDB."""
    collection = get_collection(workspace)

    # Query all chunks with this doc_id
    results = collection.get(
        where={"doc_id": doc_id},
        include=[],
    )

    if results["ids"]:
        collection.delete(ids=results["ids"])
        logger.info(
            "Removed %d chunks for doc_id=%s from collection 'kb_%s'",
            len(results["ids"]), doc_id, workspace,
        )
        return len(results["ids"])

    return 0


def query_collection(
    workspace: str,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Query the workspace's ChromaDB collection for relevant chunks.

    Returns a list of dicts with keys: text, filename, score, chunk_index.
    """
    collection = get_collection(workspace)

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results["documents"] and results["documents"][0]:
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0

            chunks.append({
                "text": doc_text,
                "filename": meta.get("filename", "unknown"),
                "score": round(1.0 - distance, 4),  # Convert distance to similarity
                "chunk_index": meta.get("chunk_index", 0),
                "doc_id": meta.get("doc_id", ""),
            })

    return chunks


def clear_collection(workspace: str) -> int:
    """Delete all chunks from a workspace's collection. Returns count removed."""
    client = get_chroma_client()
    collection_name = f"kb_{workspace}"

    try:
        collection = client.get_collection(name=collection_name)
        count = collection.count()
        client.delete_collection(name=collection_name)
        logger.info("Cleared collection '%s': %d chunks removed", collection_name, count)
        return count
    except Exception:
        return 0


def get_collection_stats(workspace: str) -> dict:
    """Get stats about a workspace's ChromaDB collection."""
    try:
        collection = get_collection(workspace)
        return {
            "total_chunks": collection.count(),
            "collection_name": f"kb_{workspace}",
        }
    except Exception:
        return {"total_chunks": 0, "collection_name": f"kb_{workspace}"}
