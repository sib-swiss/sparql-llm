import os
import time

import pandas as pd
from endpoint_schema import EndpointSchema
from langchain_core.documents import Document
from qdrant_client import models

from sparql_llm.config import embedding_model, qdrant_client

QUERIES_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "queries.csv")
VECTORDB_URL = "http://localhost:6334"


def init_vectordb(
    endpoint_url: str,
    graph: str,
    limit_schema: dict[str, float],
    max_workers: int,
    force_recompute: bool,
    schema_path: str,
) -> None:
    """Initialize the vectordb with example queries and schema information from the SPARQL endpoints"""
    docs: list[Document] = []

    # Index example queries
    if graph == "https://text2sparql.aksw.org/2025/dbpedia/":
        examples = ["QALD-9+", "LC-QuAD"]
    elif graph == "https://text2sparql.aksw.org/2025/corporate/":
        examples = ["Generated-CK"]

    queries = pd.read_csv(QUERIES_FILE)
    queries = queries[queries["dataset"].isin(examples)].reset_index(drop=True)
    docs += queries.apply(
        lambda q: Document(
            page_content=q["question"],
            metadata={
                "question": q["question"],
                "anser": q["query"],
                "endpoint_url": endpoint_url,
                "query_type": "SelectQuery"
                if q["query type"] == "SELECT"
                else "AskQuery"
                if q["query type"] == "ASK"
                else "",
                "doc_type": "SPARQL endpoints query examples",
            },
        ),
        axis=1,
    ).tolist()

    # Index schema information
    start_time = time.time()
    schema = EndpointSchema(
        endpoint_url=endpoint_url,
        graph=graph,
        limit_schema=limit_schema,
        max_workers=max_workers,
        force_recompute=force_recompute,
        schema_path=schema_path,
    ).get_schema()

    docs += schema.apply(
        lambda c: Document(
            page_content=c["name"],
            metadata={
                "desc": f"- Class URI: {c['class']}\n\t - Predicates:\n"
                + "\n".join(
                    [
                        f"\t\t {p}" + (f" : ({c['predicates'][p][0]})" if c["predicates"][p] else "")
                        for p in c["predicates"].keys()
                    ]
                ),
                "doc_type": "classes",
            },
        ),
        axis=1,
    ).tolist()

    elapsed_time = time.time() - start_time
    print(f"Schema information built time: {elapsed_time / 60:.2f} minutes")

    # Generate embeddings and loads documents into the vectordb
    print(f"Generating embeddings for {len(docs)} documents")
    start_time = time.time()

    embeddings = list(embedding_model.embed([d.page_content for d in docs]))
    qdrant_client.upsert(
        collection_name=f"text2sparql-{graph.split('/')[-2]}",
        points=models.Batch(
            ids=list(range(1, len(docs) + 1)),
            vectors=[emb.tolist() for emb in embeddings],
            payloads=[doc.metadata for doc in docs],
        ),
    )

    print(f"Done generating and indexing {len(docs)} documents into the vectordb in {time.time() - start_time} seconds")


if __name__ == "__main__":
    # Init vectordb for corporate dataset
    init_vectordb(
        endpoint_url="http://localhost:8890/sparql/",
        graph="https://text2sparql.aksw.org/2025/corporate/",
        limit_schema={
            "top_classes_percentile": 0,
            "top_n_predicates": 20,
            "top_n_ranges": 1,
        },
        max_workers=4,
        force_recompute=True,
        schema_path=os.path.join("data", "benchmarks", "Text2SPARQL", "schemas", "corporate_schema.json"),
    )
    # Init vectordb for dbpedia dataset
    init_vectordb(
        endpoint_url="http://localhost:8890/sparql/",
        graph="https://text2sparql.aksw.org/2025/dbpedia/",
        limit_schema={
            "top_classes_percentile": 0,
            "top_n_predicates": 20,
            "top_n_ranges": 1,
        },
        max_workers=4,
        force_recompute=True,
        schema_path=os.path.join("data", "benchmarks", "Text2SPARQL", "schemas", "dbpedia_schema.json"),
    )
