import os
import time

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
import pandas as pd

from expasy_agent.config import settings
from expasy_agent.nodes.retrieval_docs import make_dense_encoder

QUERIES_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'queries.csv')
ENDPOINT_URL = 'http://localhost:8890/sparql/'
VECTORDB_URL = 'http://localhost:6334'
VECTORDB_COLLECTION_NAME = 'text2sparql'

def init_vectordb() -> None:
    """Initialize the vectordb with example queries from the SPARQL endpoints"""
    docs: list[Document] = []

    queries = pd.read_csv(QUERIES_FILE)
    queries = queries[queries['dataset'] != 'Text2SPARQL'].reset_index(drop=True)
    docs = queries.apply(lambda q: Document(page_content=q['question'], 
                                            metadata = {'question': q['question'],
                                                        'anser': q['query'],
                                                        'endpoint_url': ENDPOINT_URL,
                                                        'query_type': 'SelectQuery' if q['query type'] == 'SELECT' else 'AskQuery' if q['query type'] == 'ASK' else '',
                                                        'doc_type': 'SPARQL endpoints query examples'}), axis=1).tolist()


    print(f"Generating embeddings for {len(docs)} documents")
    start_time = time.time()

    # Generate embeddings and loads documents into the vectordb
    QdrantVectorStore.from_documents(
        docs,
        # client=qdrant_client,
        url=VECTORDB_URL,
        prefer_grpc=True,
        collection_name=VECTORDB_COLLECTION_NAME,
        force_recreate=True,
        embedding=make_dense_encoder(settings.embedding_model),
        # sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
        # retrieval_mode=RetrievalMode.HYBRID,
    )

    print(
        f"Done generating and indexing {len(docs)} documents into the vectordb in {time.time() - start_time} seconds"
    )

if __name__ == "__main__":
    init_vectordb()