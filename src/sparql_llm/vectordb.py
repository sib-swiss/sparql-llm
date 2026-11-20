"""Embedded LanceDB vector store, searched with hybrid search: dense vectors and BM25 full-text search, fused with
Reciprocal Rank Fusion. Embeddings are computed locally with fastembed (ONNX, no torch).

- `docs` table: SPARQL query examples, classes schemas and resources information. LanceDB generates their embeddings
  itself on insert and search, with a fastembed embedding function registered in its registry.
- `entities` table (experimental): entities of the endpoints, embedded beforehand in batches, optionally on GPU."""

import time
from functools import cache
from typing import Any

import lancedb
import numpy as np
from fastembed import TextEmbedding
from lancedb.embeddings import TextEmbeddingFunction, get_registry, register
from lancedb.pydantic import LanceModel
from langchain_core.documents import Document

from sparql_llm.config import settings
from sparql_llm.utils import logger


@cache
def fastembed_model(name: str) -> TextEmbedding:
    """Loaded on first use, it takes a few seconds (and downloads the model the first time)"""
    return TextEmbedding(name, cache_dir=settings.fastembed_cache_path)


@register("fastembed")
class FastEmbedEmbeddings(TextEmbeddingFunction):
    name: str = settings.embedding_model

    def ndims(self) -> int:
        return TextEmbedding.get_embedding_size(self.name)

    def generate_embeddings(self, texts: list[str] | np.ndarray, *args: Any, **kwargs: Any) -> list[np.ndarray | None]:
        return list(fastembed_model(self.name).embed(list(texts)))


# Model set explicitly to be stored in the table metadata: searches of an index use the model it was built with
embedder = get_registry().get("fastembed").create(name=settings.embedding_model)


# `list[float]` vectors with a `VectorField` are stored as fixed size lists of the embedder dimension
class Doc(LanceModel):
    doc_type: str
    # Embedded and full-text indexed: question of a query example, label of a class, or resource description
    question: str = embedder.SourceField()
    # SPARQL query of an example, ShEx shape of a class, or resource information
    answer: str
    endpoint_url: str
    iri: str
    vector: list[float] = embedder.VectorField()


class Entity(LanceModel):
    label: str
    iri: str
    endpoint_url: str
    entity_type: str
    # Embedded beforehand in batches, no source field so LanceDB does not embed them on insert
    vector: list[float] = embedder.VectorField()


@cache
def db() -> lancedb.DBConnection:
    return lancedb.connect(settings.lancedb_path)


def count_docs() -> int:
    """Number of documents in the index, 0 when it does not exist"""
    return db().open_table(settings.docs_table).count_rows() if settings.docs_table in db().list_tables().tables else 0


def index_model() -> str | None:
    """Embedding model the index was built with, None when it does not exist"""
    if settings.docs_table not in db().list_tables().tables:
        return None
    return getattr(db().open_table(settings.docs_table).embedding_functions["vector"].function, "name", None)


def index_docs(docs: list[Document]) -> None:
    """(Re)create the index with the given documents, embedded by LanceDB, and their full-text search index"""
    start = time.time()
    logger.info(f"Generating embeddings for {len(docs)} documents with {settings.embedding_model}")
    rows = [
        {
            "doc_type": str(doc.metadata.get("doc_type", "")),
            "question": doc.page_content,
            "answer": str(doc.metadata.get("answer") or ""),
            "endpoint_url": str(doc.metadata.get("endpoint_url") or ""),
            "iri": str(doc.metadata.get("iri") or ""),
        }
        for doc in docs
    ]
    table = db().create_table(settings.docs_table, schema=Doc, mode="overwrite")
    table.add(rows)
    table.create_fts_index("question", replace=True)
    logger.info(f"Indexed {len(rows)} documents in {settings.lancedb_path} in {time.time() - start:.1f}s")


def search_docs(queries: list[str], where: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Hybrid search of the documents matching the `where` SQL filter (e.g. `doc_type = 'x'`) for each query,
    deduplicated by their answer (or question when they have none), in the order of the queries. The RRF score of each
    document is in `_relevance_score`"""
    if not count_docs():
        raise LookupError("The index is empty, build it with `uv run python -m sparql_llm.indexing.index_resources`")
    table = db().open_table(settings.docs_table)
    results: dict[str, dict[str, Any]] = {}
    for query in queries:
        search = table.search(query, query_type="hybrid")
        if where:
            search = search.where(where, prefilter=True)
        for hit in search.limit(limit or settings.default_number_of_retrieved_docs).to_list():
            results.setdefault(hit["answer"] or hit["question"], hit)
    return list(results.values())


def index_entities(docs: list[Document], gpu: bool = False, batch_size: int = 1000) -> None:
    """(Re)create the entities index, embedding their labels in batches, with a vector index (entities are counted in
    millions) and a full-text search index"""
    start = time.time()
    model = TextEmbedding(
        settings.embedding_model,
        cache_dir=settings.fastembed_cache_path,
        providers=["CUDAExecutionProvider"] if gpu else None,
    )
    table = db().create_table(settings.entities_table, schema=Entity, mode="overwrite")
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        vectors = model.embed([d.page_content for d in batch])
        table.add(
            [
                {
                    "label": str(d.metadata.get("label", "")),
                    "iri": str(d.metadata.get("iri", "")),
                    "endpoint_url": str(d.metadata.get("endpoint_url", "")),
                    "entity_type": str(d.metadata.get("entity_type", "")),
                    "vector": v,
                }
                for d, v in zip(batch, vectors, strict=True)
            ]
        )
        logger.info(f"Embedded {i + len(batch)}/{len(docs)} entities, {(time.time() - start) / 60:.1f} minutes elapsed")
    # Merge the fragments created by each batch before building the indexes
    table.optimize()
    table.create_index(metric="cosine", vector_column_name="vector", replace=True)
    table.create_fts_index("label", replace=True)
    logger.info(f"Indexed {len(docs)} entities in {(time.time() - start) / 60:.1f} minutes")


def search_entities(texts: list[str], limit: int = 5) -> list[list[dict[str, Any]]]:
    """Hybrid search of the entities matching each text, deduplicated by IRI and endpoint"""
    table = db().open_table(settings.entities_table)
    results = []
    for text, vector in zip(texts, fastembed_model(settings.embedding_model).embed(texts), strict=True):
        hits = table.search(query_type="hybrid").vector(vector).text(text).limit(limit).to_list()
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for hit in hits:
            unique.setdefault((hit["iri"], hit["endpoint_url"]), hit)
        results.append(list(unique.values()))
    return results
