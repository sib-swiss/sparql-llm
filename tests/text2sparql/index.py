import os
import time

import pandas as pd
from api import DATASETS_ENDPOINTS, embedding_model, get_dataset_id_from_iri, qdrant_client
from endpoint_schema import EndpointSchema
from langchain_core.documents import Document
from qdrant_client import models
from qdrant_client.http.models import Distance, VectorParams

QUERIES_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "queries.csv")


def init_vectordb(
    endpoint_url: str,
    dataset_iri: str,
    limit_schema: dict[str, float],
    max_workers: int,
    force_recompute: bool,
) -> None:
    """Initialize the vectordb with example queries and schema information from the SPARQL endpoints"""
    docs: list[Document] = []

    # Index example queries
    examples = ["Generated-CK"] if "corporate" in dataset_iri else ["QALD-9+", "LC-QuAD"]

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
        limit_schema=limit_schema,
        max_workers=max_workers,
        force_recompute=force_recompute,
        schema_path=os.path.join("data", f"{get_dataset_id_from_iri(dataset_iri)}_schema.json"),
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

    collection_name = f"text2sparql-{get_dataset_id_from_iri(dataset_iri)}"
    # Ensure collection exists before upserting
    if not qdrant_client.collection_exists(collection_name):
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=embedding_model.embedding_size, distance=Distance.COSINE),
        )

    qdrant_client.upsert(
        collection_name=collection_name,
        points=models.Batch(
            ids=list(range(1, len(docs) + 1)),
            vectors=[emb.tolist() for emb in embeddings],
            payloads=[doc.metadata for doc in docs],
        ),
    )

    print(f"Done generating and indexing {len(docs)} documents into the vectordb in {time.time() - start_time} seconds")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize vectordb for a dataset IRI")
    parser.add_argument(
        "dataset_iri",
        help="Dataset IRI, e.g. https://text2sparql.aksw.org/2025/dbpedia/",
    )
    args = parser.parse_args()

    dataset_iri = args.dataset_iri

    # Init vectordb for the specified dataset
    init_vectordb(
        endpoint_url=DATASETS_ENDPOINTS[dataset_iri],
        dataset_iri=dataset_iri,
        limit_schema={
            "top_classes_percentile": 0,
            "top_n_predicates": 20,
            "top_n_ranges": 1,
        },
        max_workers=4,
        force_recompute=True,
    )
