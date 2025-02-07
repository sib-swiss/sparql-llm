import time

import requests
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from rdflib import RDF, Dataset, Namespace
from sparql_llm.sparql_examples_loader import SparqlExamplesLoader
from sparql_llm.sparql_void_shapes_loader import SparqlVoidShapesLoader
from sparql_llm.utils import get_prefixes_for_endpoints

from expasy_agent.config import Configuration, settings
from expasy_agent.nodes.retrieval import make_dense_encoder

SCHEMA = Namespace("http://schema.org/")

# configuration = Configuration()

def load_schemaorg_description(endpoint: dict[str, str]) -> list[Document]:
    """Extract datasets descriptions from the schema.org metadata in homepage of the endpoint"""
    docs = []
    try:
        resp = requests.get(
            endpoint["homepage"],
            headers={
                # "User-Agent": "BgeeBot/1.0",
                # Adding a user-agent to make it look like we are a google bot to trigger SSR
                "User-Agent": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.96 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html) X-Middleton/1",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch the webpage: {resp.status_code}")
        # print(resp.text)

        # Parse HTML and find the JSON-LD script tag
        soup = BeautifulSoup(resp.content, "html.parser")
        json_ld_tags = soup.find_all("script", type="application/ld+json")
        if not json_ld_tags:
            raise Exception("No JSON-LD script tags found")

        g = Dataset()
        for json_ld_tag in json_ld_tags:
            json_ld_content = str(json_ld_tag.string)
            # print(json_ld_content, type(json_ld_content))
            if json_ld_content:
                # TODO: error here now, even if JSON-LD is valid
                g.parse(data=json_ld_content, format="json-ld")
                # json_ld_content = json.loads(json_ld_content)
                question = f"What are the general metadata about {endpoint['label']} resource? (description, creators, maintainers, license, dates, version, etc)"
                docs.append(
                    Document(
                        page_content=question,
                        metadata={
                            "question": question,
                            "answer": json_ld_content,
                            # "answer": f"```json\n{json_ld_content}\n```",
                            "iri": endpoint["homepage"],
                            "endpoint_url": endpoint["endpoint_url"],
                            "doc_type": "General information",
                        },
                    )
                )

        # Concat all schema:description of all classes in the graph
        descs = set()
        # print(len(g))
        # print(g.serialize(format="turtle"))
        for s, _p, _o in g.triples((None, RDF.type, None)):
            for _sd, _pd, desc in g.triples((s, SCHEMA.description, None)):
                descs.add(str(desc))

        if len(descs) == 0:
            raise Exception("No schema:description found in the JSON-LD script tag")
        question = f"What is the SIB resource {endpoint['label']} about?"
        docs.append(
            Document(
                page_content=question,
                metadata={
                    "question": question,
                    "answer": "\n".join(descs),
                    "endpoint_url": endpoint["endpoint_url"],
                    "iri": endpoint["homepage"],
                    "doc_type": "General information",
                },
            )
        )
        # print("\n".join(descs))
    except Exception as e:
        print(f"Error while fetching schema.org metadata from {endpoint['label']}: {e}")
    return docs


def load_ontology(endpoint: dict[str, str]) -> list[Document]:
    """Get documents from the OWL ontology URL given for each SPARQL endpoint."""
    if "ontology" not in endpoint:
        return []
    # g = Dataset(store="Oxigraph")
    g = Dataset()
    try:
        # Hackity hack to handle UniProt ontology in XML format but with .owl extension
        g.parse(endpoint["ontology"], format="ttl")
    except Exception:
        g.parse(endpoint["ontology"], format="xml")

    ontology_chunk_size = 3000
    ontology_chunk_overlap = 200

    # Chunking the ontology is done here
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=ontology_chunk_size, chunk_overlap=ontology_chunk_overlap
    )
    splits = text_splitter.create_documents([g.serialize(format="ttl")])

    docs = [
        Document(
            page_content=split.page_content,
            metadata={
                "question": split.page_content,
                "answer": "",
                "endpoint_url": endpoint["endpoint_url"],
                "iri": endpoint["ontology"],
                "doc_type": "ontology",
            },
        )
        for split in splits
    ]
    print(f"Extracted {len(docs)} chunks for {endpoint['label']} ontology")
    return docs


def init_vectordb() -> None:
    """Initialize the vectordb with example queries and ontology descriptions from the SPARQL endpoints"""
    docs: list[Document] = []

    endpoints_urls = [endpoint["endpoint_url"] for endpoint in settings.endpoints]
    prefix_map = get_prefixes_for_endpoints(endpoints_urls)

    for endpoint in settings.endpoints:
        print(f"\n  🔎 Getting metadata for {endpoint['label']} at {endpoint['endpoint_url']}")
        queries_loader = SparqlExamplesLoader(endpoint["endpoint_url"], verbose=True)
        docs += queries_loader.load()

        void_loader = SparqlVoidShapesLoader(
            endpoint["endpoint_url"],
            prefix_map=prefix_map,
            verbose=True,
        )
        docs += void_loader.load()

        docs += load_schemaorg_description(endpoint)
        # NOTE: we dont use the ontology for now, schema from shex is better
        # docs += load_ontology(endpoint)

    # NOTE: Manually add infos for UniProt since we cant retrieve it for now. Taken from https://www.uniprot.org/help/about
    uniprot_description_question = "What is the SIB resource UniProt about?"
    docs.append(
        Document(
            page_content=uniprot_description_question,
            metadata={
                "question": uniprot_description_question,
                "answer": """The Universal Protein Resource (UniProt) is a comprehensive resource for protein sequence and annotation data. The UniProt databases are the UniProt Knowledgebase (UniProtKB), the UniProt Reference Clusters (UniRef), and the UniProt Archive (UniParc). The UniProt consortium and host institutions EMBL-EBI, SIB and PIR are committed to the long-term preservation of the UniProt databases.

UniProt is a collaboration between the European Bioinformatics Institute (EMBL-EBI), the SIB Swiss Institute of Bioinformatics and the Protein Information Resource (PIR). Across the three institutes more than 100 people are involved through different tasks such as database curation, software development and support.

EMBL-EBI and SIB together used to produce Swiss-Prot and TrEMBL, while PIR produced the Protein Sequence Database (PIR-PSD). These two data sets coexisted with different protein sequence coverage and annotation priorities. TrEMBL (Translated EMBL Nucleotide Sequence Data Library) was originally created because sequence data was being generated at a pace that exceeded Swiss-Prot's ability to keep up. Meanwhile, PIR maintained the PIR-PSD and related databases, including iProClass, a database of protein sequences and curated families. In 2002 the three institutes decided to pool their resources and expertise and formed the UniProt consortium.

The UniProt consortium is headed by Alex Bateman, Alan Bridge and Cathy Wu, supported by key staff, and receives valuable input from an independent Scientific Advisory Board.
""",
                "endpoint_url": "https://sparql.uniprot.org/sparql/",
                "iri": "http://www.uniprot.org/help/about",
                "doc_type": "General information",
            },
        )
    )

    print(f"Generating embeddings for {len(docs)} documents")
    start_time = time.time()

    # Using LangChain
    QdrantVectorStore.from_documents(
        docs,
        # url="http://localhost:6333/",
        url=settings.vectordb_url,
        collection_name=settings.docs_collection_name,
        embedding=make_dense_encoder(settings.embedding_model),
        # sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
        # retrieval_mode=RetrievalMode.HYBRID,
        prefer_grpc=True,
        force_recreate=True,
    )

    # Using fastembed and Qdrant client directly
    # from qdrant_client import models
    # from qdrant_client.http.models import Distance, VectorParams
    # vectordb = get_vectordb(settings.vectordb_url)
    # if vectordb.collection_exists(settings.docs_collection_name):
    #     vectordb.delete_collection(settings.docs_collection_name)
    # vectordb.create_collection(
    #     collection_name=settings.docs_collection_name,
    #     vectors_config=VectorParams(size=settings.embedding_dimensions, distance=Distance.COSINE),
    # )
    # embedding_model = get_embedding_model()
    # embeddings = embedding_model.embed([q.page_content for q in docs])

    # vectordb.upsert(
    #     collection_name=settings.docs_collection_name,
    #     points=models.Batch(
    #         ids=list(range(1, len(docs) + 1)),
    #         vectors=embeddings,
    #         payloads=[doc.metadata for doc in docs],
    #     ),
    #     # wait=False, # Waiting for indexing to finish or not
    # )

    print(
        f"Done generating and indexing {len(docs)} documents into the vectordb in {time.time() - start_time} seconds"
    )


if __name__ == "__main__":
    init_vectordb()
