import re
from typing import Annotated, Dict, List, Union

from bs4 import BeautifulSoup
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse
from fastembed import TextEmbedding
from pydantic import BaseModel, conint
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
)
from SPARQLWrapper import JSON, SPARQLWrapper
from starlette.middleware.cors import CORSMiddleware

# Initialize FastEmbed and Qdrant Client
embedding_model = TextEmbedding("BAAI/bge-large-en-v1.5")
embedding_dimensions = 1024

vectordb = QdrantClient(
    host="qdrant",
    prefer_grpc=True,
)
QUERIES_COLLECTION="expasy-queries"


endpoints = {
    "UniProt": "https://sparql.uniprot.org/sparql/",
    "Bgee": "https://www.bgee.org/sparql/",
}

get_queries = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?comment ?query
WHERE
{
    ?sq a sh:SPARQLExecutable ;
        rdfs:label|rdfs:comment ?comment ;
        sh:select|sh:ask|sh:construct|sh:describe ?query .
}"""

get_prefixes = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


def remove_a_tags(html_text: str) -> str:
    """Remove all <a> tags from the queries descriptions"""
    soup = BeautifulSoup(html_text, "html.parser")
    for a_tag in soup.find_all("a"):
        a_tag.replace_with(a_tag.text)
    return soup.get_text()

def init_queries_vectordb()-> None:
    queries = []
    for endpoint_name, endpoint_url in endpoints.items():
        sparql_endpoint = SPARQLWrapper(endpoint_url)
        sparql_endpoint.setReturnFormat(JSON)

        sparql_endpoint.setQuery(get_prefixes)
        results = sparql_endpoint.query().convert()
        prefix_map = {}
        for row in results["results"]["bindings"]:
            prefix_map[row["prefix"]["value"]] = row["namespace"]["value"]

        sparql_endpoint.setQuery(get_queries)
        results = sparql_endpoint.query().convert()
        print(f"Found {len(results['results']['bindings'])} queries for {endpoint_url}")

        for row in results["results"]["bindings"]:
            query = row["query"]["value"]
            # Add prefixes to queries
            for prefix, namespace in prefix_map.items():
                prefix_str = f"PREFIX {prefix}: <{namespace}>"
                if not re.search(prefix_str, query) and re.search(f"[(| |\u00a0|/]{prefix}:", query):
                    query = f"{prefix_str}\n{query}"
            queries.append({
                "endpoint": endpoint_url,
                "comment": f"{endpoint_name}: {remove_a_tags(row['comment']['value'])}",
                "query": query,
            })

    if not vectordb.collection_exists(QUERIES_COLLECTION):
        vectordb.create_collection(
            collection_name=QUERIES_COLLECTION,
            vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE),
        )

    questions = [q["comment"] for q in queries]
    print(len(questions))
    output = embedding_model.embed(questions)
    print(f"Done generating embeddings for {len(questions)} queries")

    vectordb.upsert(
        collection_name=QUERIES_COLLECTION,
        points=models.Batch(
            ids=list(range(1, len(queries) + 1)),
            vectors=[embeddings.tolist() for embeddings in output],
            payloads=queries,
        ),
    )

if __name__ == "__main__":
    init_queries_vectordb()
    print(f"VectorDB initialized with {vectordb.get_collection(QUERIES_COLLECTION).points_count} vectors")
