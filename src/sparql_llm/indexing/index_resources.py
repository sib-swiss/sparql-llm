import time

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from markdownify import markdownify
from qdrant_client import models
from qdrant_client.http.models import Distance, VectorParams
from rdflib import RDF, Dataset, Namespace

from sparql_llm import SparqlExamplesLoader, SparqlInfoLoader, SparqlVoidShapesLoader
from sparql_llm.config import embedding_model, qdrant_client, settings
from sparql_llm.loaders.sparql_info_loader import GENERAL_INFO_DOC_TYPE
from sparql_llm.utils import SparqlEndpointLinks, get_prefixes_and_schema_for_endpoints

SCHEMA = Namespace("http://schema.org/")

# DOC_TYPE = "General information"


def load_schemaorg_description(endpoint: SparqlEndpointLinks) -> list[Document]:
    """Extract datasets descriptions from the schema.org metadata in homepage of the endpoint"""
    docs = []
    homepage_url = endpoint.get("homepage_url")
    try:
        if homepage_url:
            resp = httpx.get(
                homepage_url,
                headers={
                    # "User-Agent": "BgeeBot/1.0",
                    # Adding a user-agent to make it look like we are a google bot to trigger SSR on Bgee
                    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.96 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html) X-Middleton/1",
                },
                timeout=10,
                follow_redirects=True,
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
                    question = f"What are the general metadata about {endpoint.get('label')} resource? (description, creators, maintainers, license, dates, version, etc)"
                    docs.append(
                        Document(
                            page_content=question,
                            metadata={
                                "question": question,
                                "answer": json_ld_content,
                                # "answer": f"```json\n{json_ld_content}\n```",
                                "iri": homepage_url,
                                "endpoint_url": endpoint["endpoint_url"],
                                "doc_type": GENERAL_INFO_DOC_TYPE,
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
            question = f"What is the SIB resource {endpoint.get('label')} about?"
            docs.append(
                Document(
                    page_content=question,
                    metadata={
                        "question": question,
                        "answer": "\n".join(descs),
                        "endpoint_url": endpoint["endpoint_url"],
                        "iri": homepage_url,
                        "doc_type": GENERAL_INFO_DOC_TYPE,
                    },
                )
            )
            # print("\n".join(descs))
    except Exception as e:
        print(f"Error while fetching schema.org metadata from {endpoint.get('label')}: {e}")
    return docs


# Which tools can I use for enrichment analysis?


def load_expasy_resources_infos(file: str = "expasy_resources_metadata.csv") -> list[Document]:
    """Get documents for all SIB expasy resources defined in expasy_resources_metadata.csv"""
    df = pd.read_csv(file)
    docs: list[Document] = []
    for _, row in df.iterrows():
        # Long description of the resource
        doc = Document(
            page_content=f"[{row['title']}]({row['url']}) ({row['category']}): {row['description']}",
            metadata={
                "iri": row["url"],
                "doc_type": GENERAL_INFO_DOC_TYPE,
            },
        )
        docs.append(doc)

        # Short description and ontology terms
        if isinstance(row.get("ontology_terms"), str):
            doc = Document(
                page_content=f"[{row['title']}]({row['url']}) ({row['category']}): {row['short_description']}.\n\n{row['ontology_terms']}",
                metadata={
                    "iri": row["url"],
                    "doc_type": GENERAL_INFO_DOC_TYPE,
                },
            )
            docs.append(doc)

        # Info about the resource maintainers
        if isinstance(row.get("group_info"), str):
            detail_doc = Document(
                page_content=f"[{row['title']}]({row['url']}): {markdownify(row['group_info'])} License: {row.get('license', 'not specified')}",
                metadata={
                    "iri": row["url"],
                    "doc_type": GENERAL_INFO_DOC_TYPE,
                },
            )
            docs.append(detail_doc)

    docs.append(
        Document(
            page_content="How many resources are there in the Expasy catalog?",
            # page_content=f"There are {len(df)} resources in the Expasy catalog",
            metadata={
                # "iri": row["url"],
                "answer": str(len(df)),
                "doc_type": GENERAL_INFO_DOC_TYPE,
            },
        )
    )

    print(f"Extracted {len(docs)} documents from {file}")
    return docs


def init_vectordb() -> None:
    """Initialize the vectordb with example queries and ontology descriptions from the SPARQL endpoints"""
    docs: list[Document] = []
    prefix_map, _void_schema = get_prefixes_and_schema_for_endpoints(settings.endpoints)

    # Gets documents from the SPARQL endpoints
    for endpoint in settings.endpoints:
        print(f"\n  🔎 Getting metadata for {endpoint.get('label')} at {endpoint['endpoint_url']}")
        docs += SparqlExamplesLoader(
            endpoint["endpoint_url"],
            examples_file=endpoint.get("examples_file"),
        ).load()

        docs += SparqlVoidShapesLoader(
            endpoint["endpoint_url"],
            prefix_map=prefix_map,
            void_file=endpoint.get("void_file"),
            examples_file=endpoint.get("examples_file"),
        ).load()

        docs += load_schemaorg_description(endpoint)
        # NOTE: we dont use the ontology for now, schema from shex is better
        # docs += load_ontology(endpoint)

        # NOTE: Manually add infos for UniProt since we cant retrieve it for now. Taken from https://www.uniprot.org/help/about
        if "sparql.uniprot.org" in endpoint["endpoint_url"]:
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
                        "endpoint_url": endpoint["endpoint_url"],
                        "iri": "http://www.uniprot.org/help/about",
                        "doc_type": GENERAL_INFO_DOC_TYPE,
                    },
                )
            )

    # Add some documents for general information about the resources
    docs += SparqlInfoLoader(
        settings.endpoints,
        source_iri="https://www.expasy.org/",
        service_label=settings.app_name,
        org_label="from the Swiss Institute of Bioinformatics (SIB)",
    ).load()

    try:
        docs += load_expasy_resources_infos()
    except Exception as _e:
        print("Skipping loading Expasy resources metadata")

    print(f"Generating embeddings for {len(docs)} documents")
    start_time = time.time()

    # Initialize the collection
    if qdrant_client.collection_exists(settings.docs_collection_name):
        qdrant_client.delete_collection(settings.docs_collection_name)
    qdrant_client.create_collection(
        collection_name=settings.docs_collection_name,
        vectors_config=VectorParams(size=settings.embedding_dimensions, distance=Distance.COSINE),
    )

    # Generate embeddings with the fastembed `TextEmbedding` instance and upload directly to Qdrant
    # https://qdrant.tech/documentation/fastembed/fastembed-rerankers/
    embeddings = list(embedding_model.embed([d.page_content for d in docs]))
    qdrant_client.upsert(
        collection_name=settings.docs_collection_name,
        points=models.Batch(
            ids=list(range(1, len(docs) + 1)),
            vectors=[emb.tolist() for emb in embeddings],
            payloads=[doc.metadata for doc in docs],
        ),
    )
    print(f"Done generating and indexing {len(docs)} documents into the vectordb in {time.time() - start_time} seconds")

    # Using langchain vectorstore wrapper
    # from langchain_qdrant import QdrantVectorStore
    # vectorstore = QdrantVectorStore(
    #     client=qdrant_client,
    #     collection_name=settings.docs_collection_name,
    #     embedding=make_dense_encoder(settings.embedding_model),
    #     # sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
    #     # retrieval_mode=RetrievalMode.HYBRID,
    # )
    # vectorstore.add_documents(docs)


if __name__ == "__main__":
    init_vectordb()


# # Not used anymore
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# def load_ontology(endpoint: dict[str, str]) -> list[Document]:
#     """Get documents from the OWL ontology URL given for each SPARQL endpoint."""
#     if "ontology" not in endpoint:
#         return []
#     # g = Dataset(store="Oxigraph")
#     g = Dataset()
#     try:
#         # Hackity hack to handle UniProt ontology in XML format but with .owl extension
#         g.parse(endpoint["ontology"], format="ttl")
#     except Exception:
#         g.parse(endpoint["ontology"], format="xml")

#     ontology_chunk_size = 3000
#     ontology_chunk_overlap = 200

#     # Chunking the ontology is done here
#     text_splitter = RecursiveCharacterTextSplitter(
#         chunk_size=ontology_chunk_size, chunk_overlap=ontology_chunk_overlap
#     )
#     splits = text_splitter.create_documents([g.serialize(format="ttl")])

#     docs = [
#         Document(
#             page_content=split.page_content,
#             metadata={
#                 "question": split.page_content,
#                 "answer": "",
#                 "endpoint_url": endpoint["endpoint_url"],
#                 "iri": endpoint["ontology"],
#                 "doc_type": "ontology",
#             },
#         )
#         for split in splits
#     ]
#     print(f"Extracted {len(docs)} chunks for {endpoint['label']} ontology")
#     return docs
