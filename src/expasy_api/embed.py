import re

from bs4 import BeautifulSoup
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
)
from SPARQLWrapper import JSON, SPARQLWrapper

# https://qdrant.github.io/fastembed/examples/Supported_Models/
# TextEmbedding.list_supported_models()
embedding_model = TextEmbedding("BAAI/bge-large-en-v1.5")
# embedding_model = TextEmbedding("BAAI/bge-base-en-v1.5")
embedding_dimensions = 1024

vectordb = QdrantClient(
    host="search-engine",
    prefer_grpc=True,
)
QUERIES_COLLECTION="expasy-queries"


endpoints = {
    "UniProt": "https://sparql.uniprot.org/sparql/",
    "Bgee": "https://www.bgee.org/sparql/",
    "Ortholog MAtrix (OMA)": "https://sparql.omabrowser.org/sparql/",
    "Rhea reactions": "https://sparql.rhea-db.org/sparql/",
    "GlyConnect": "https://glyconnect.expasy.org/sparql",
    "MetaNetx": "https://rdf.metanetx.org/sparql/",
    "NextProt": "https://sparql.nextprot.org",
    # "SwissLipids": "https://sparql.swisslipids.org/sparql/",
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


def init_vectordb(vectordb_host: str = "search-engine")-> None:
    vectordb = QdrantClient(
        host=vectordb_host,
        prefer_grpc=True,
    )
    queries = []
    for endpoint_name, endpoint_url in endpoints.items():
        try:
            sparql_endpoint = SPARQLWrapper(endpoint_url)
            sparql_endpoint.setReturnFormat(JSON)

            # Add SPARQL queries examples to the vectordb
            sparql_endpoint.setQuery(get_prefixes)
            results = sparql_endpoint.query().convert()
            prefix_map = {}
            for row in results["results"]["bindings"]:
                prefix_map[row["prefix"]["value"]] = row["namespace"]["value"]

            sparql_endpoint.setQuery(get_queries)
            results = sparql_endpoint.query().convert()
            print(f"Found {len(results['results']['bindings'])} examples queries for {endpoint_url}")

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
                    "example": query,
                    "doc_type": "sparql",
                })
        except Exception as e:
            print(f"Error while fetching queries from {endpoint_name}: {e}")

        # sparql_endpoint.setQuery(get_queries)
        # results = sparql_endpoint.query().convert()

    # OMA ontology:
    # https://github.com/qfo/OrthologyOntology/blob/master/orthOntology_v2.ttl
    # For each class get the vann:example provided which is an example of the class as turtle?

    ## Query to get VoID metadata from the SPARQL endpoint:
    # PREFIX sh: <http://www.w3.org/ns/shacl#>
    # PREFIX void: <http://rdfs.org/ns/void#>

    # SELECT DISTINCT ?class1 ?prop ?class2 ?pp1triples ?graph
    # FROM <https://sparql.uniprot.org/.well-known/void>
    # FROM <https://sparql.uniprot.org/.well-known/sparql-examples>
    # WHERE {
    # {
    #     ?s <http://www.w3.org/ns/sparql-service-description#graph> ?graph .
    #     ?graph void:classPartition ?cp1 .
    #     ?cp1 void:class ?class1 ;
    #         void:propertyPartition ?pp1 .
    #     ?pp1 void:property ?prop ;
    #         void:triples ?pp1triples ;
    #         void:classPartition ?cp2 .
    #     ?cp2 void:class ?class2 .

    # #    ?graph void:classPartition ?cp3 .
    # #    ?cp3 void:class ?class2 .
    # }
    # } ORDER BY DESC(?pp1triples)



    if not vectordb.collection_exists(QUERIES_COLLECTION):
        vectordb.create_collection(
            collection_name=QUERIES_COLLECTION,
            vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE),
        )

    questions = [q["comment"] for q in queries]
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
    init_vectordb()
    print(f"VectorDB initialized with {vectordb.get_collection(QUERIES_COLLECTION).points_count} vectors")
