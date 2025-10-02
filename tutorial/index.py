from fastembed import TextEmbedding
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from sparql_llm import SparqlExamplesLoader, SparqlInfoLoader, SparqlVoidShapesLoader

# List of endpoints that will be used
# endpoints: list[SparqlEndpointLinks] = [
endpoints: list[dict[str, str]] = [
    {
        # The URL of the SPARQL endpoint from which most informations will be extracted
        "endpoint_url": "https://sparql.uniprot.org/sparql/",
        # If VoID description or SPARQL query examples are not available in the endpoint, you can provide a VoID file (local or remote URL)
        # "void_file": "../src/sparql-llm/tests/void_uniprot.ttl",
        # "void_file": "data/uniprot_void.ttl",
        # "examples_file": "data/uniprot_examples.ttl",
    },
    {
        "endpoint_url": "https://www.bgee.org/sparql/",
    },
    {
        "endpoint_url": "https://sparql.omabrowser.org/sparql/",
    },
]

embedding_model = TextEmbedding(
    "BAAI/bge-small-en-v1.5",
    # providers=["CUDAExecutionProvider"], # Replace the fastembed dependency with fastembed-gpu to use your GPUs
)
embedding_dimensions = 384

vectordb = QdrantClient(host="localhost", prefer_grpc=True)
collection_name = "sparql-docs"


def index_endpoints():
    # Get documents from the SPARQL endpoints
    docs: list[Document] = []
    for endpoint in endpoints:
        print(f"\n  🔎 Getting metadata for {endpoint['endpoint_url']}")
        docs += SparqlExamplesLoader(
            endpoint["endpoint_url"],
            examples_file=endpoint.get("examples_file"),
        ).load()

        docs += SparqlVoidShapesLoader(
            endpoint["endpoint_url"],
            void_file=endpoint.get("void_file"),
            examples_file=endpoint.get("examples_file"),
        ).load()
    docs += SparqlInfoLoader(endpoints, source_iri="https://www.expasy.org/").load()

    if vectordb.collection_exists(collection_name):
        vectordb.delete_collection(collection_name)
    vectordb.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE),
    )

    embeddings = embedding_model.embed([q.page_content for q in docs])
    vectordb.upload_collection(
        collection_name=collection_name,
        vectors=[embed.tolist() for embed in embeddings],
        payload=[doc.metadata for doc in docs],
    )

    # # Using LangChain VectorStore object
    # from langchain_qdrant import QdrantVectorStore
    # from langchain_community.embeddings import FastEmbedEmbeddings
    # QdrantVectorStore.from_documents(
    #     docs,
    #     host="localhost",
    #     # location=":memory:",
    #     # path="data/qdrant",
    #     prefer_grpc=True,
    #     collection_name="sparql-docs",
    #     force_recreate=True,
    #     embedding=FastEmbedEmbeddings(
    #         model_name="BAAI/bge-small-en-v1.5",
    #         # providers=["CUDAExecutionProvider"], # Uncomment this line to use your GPUs
    #     ),
    # )


if __name__ == "__main__":
    index_endpoints()
