"""ChromaDB persistence and multilingual-e5 embedding helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import chromadb
from chromadb.config import Settings

from .text_processing import Chunk

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-base"


def _cached_model_path(model_name: str) -> str | None:
    """Return the local Hugging Face snapshot path when one is complete enough to use."""
    if Path(model_name).is_dir():
        return model_name
    try:
        from huggingface_hub import try_to_load_from_cache

        cached_modules = try_to_load_from_cache(model_name, "modules.json")
        if isinstance(cached_modules, str) and Path(cached_modules).is_file():
            return str(Path(cached_modules).parent)
    except (ImportError, OSError):
        pass
    return None


class Embedder:
    """Apply E5's required query/passage prefixes before embedding."""

    def __init__(self, model_name: str) -> None:
        # Import lazily so `python main.py --help` stays fast on a clean machine.
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        cached_path = _cached_model_path(model_name)
        # Passing a snapshot *directory* prevents recent Transformers releases
        # from checking Hugging Face for model metadata on every later run.
        self.model = SentenceTransformer(cached_path or model_name, local_files_only=bool(cached_path))

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self.model.encode(
            [f"passage: {text}" for text in texts],
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 32,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self.model.encode(
            f"query: {text}", normalize_embeddings=True, show_progress_bar=False
        )
        return vector.tolist()

    def score_passages_against_query(self, query: str, passages: Sequence[str]) -> list[float]:
        """Return cosine similarities for a small set of already-retrieved sentences."""
        query_vector = self.embed_query(query)
        passage_vectors = self.embed_passages(passages)
        return [sum(query_value * passage_value for query_value, passage_value in zip(query_vector, vector)) for vector in passage_vectors]


def _client(db_path: Path) -> chromadb.PersistentClient:
    db_path.mkdir(parents=True, exist_ok=True)
    # This assignment is entirely local; disabling anonymous telemetry also
    # avoids noisy optional-telemetry warnings in some Chroma releases.
    return chromadb.PersistentClient(path=str(db_path), settings=Settings(anonymized_telemetry=False))


def ingest_chunks(
    chunks: Sequence[Chunk],
    db_path: Path,
    collection_name: str,
    embedder: Embedder,
) -> int:
    """Replace one collection with a freshly embedded, reproducible version."""
    client = _client(db_path)
    try:
        client.delete_collection(collection_name)
    except (ValueError, KeyError):
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "embedding_model": embedder.model_name},
    )
    batch_size = 64
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        collection.add(
            ids=[chunk.chunk_id for chunk in batch],
            documents=[chunk.text for chunk in batch],
            embeddings=embedder.embed_passages([chunk.text for chunk in batch]),
            metadatas=[
                {
                    "page": chunk.page,
                    "section": chunk.section,
                    "chunk_id": chunk.chunk_id,
                    "embedding_model": embedder.model_name,
                }
                for chunk in batch
            ],
        )
    return collection.count()


def retrieve(
    query: str,
    db_path: Path,
    collection_name: str,
    embedder: Embedder,
    top_k: int,
) -> list[dict[str, object]]:
    client = _client(db_path)
    try:
        collection = client.get_collection(collection_name)
    except ValueError as exc:
        raise RuntimeError(
            "No Chroma collection was found. Run the ingest command before asking questions."
        ) from exc
    if collection.count() == 0:
        raise RuntimeError("The Chroma collection is empty. Run ingest again.")

    results = collection.query(
        query_embeddings=[embedder.embed_query(query)],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    retrieved: list[dict[str, object]] = []
    for chunk_id, document, metadata, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # With Chroma cosine distance and normalized vectors, similarity is 1 - distance.
        score = max(-1.0, min(1.0, 1.0 - float(distance)))
        retrieved.append(
            {
                "chunk_id": chunk_id,
                "text": document,
                "metadata": metadata,
                "score": score,
            }
        )
    return retrieved
