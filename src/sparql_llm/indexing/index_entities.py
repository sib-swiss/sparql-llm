import argparse
import time
from typing import Any

from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_core.documents import Document
from qdrant_client import models

from sparql_llm.config import qdrant_client, settings
from sparql_llm.utils import query_sparql

# NOTE: Run the script to extract entities from endpoints and generate embeddings for them (long):
# ssh adsicore
# cd /mnt/scratch/sparql-llm
# docker compose -f compose.dev.yml up vectordb
# cd src/expasy-agent
# nohup VECTORDB_URL=http://localhost:6334 uv run --extra gpu src/sparql_llm/indexing/index_entities.py --gpu &


def retrieve_index_data(entity: dict, docs: list[Document], pagination: (int, int) = None) -> Any:  # type: ignore
    query = f"{entity['query']} LIMIT {pagination[0]} OFFSET {pagination[1]}" if pagination else entity["query"]
    try:
        entities_res = query_sparql(query, entity["endpoint"])["results"]["bindings"]
    except Exception as _e:
        return None
    print(f"Found {len(entities_res)} entities for {entity['label']} in {entity['endpoint']}")
    for entity_res in entities_res:
        docs.append(
            Document(
                page_content=entity_res["label"]["value"],
                metadata={
                    "label": entity_res["label"]["value"],
                    "iri": entity_res["uri"]["value"],
                    "endpoint_url": entity["endpoint"],
                    "entity_type": entity["uri"],
                },
            )
        )
    return entities_res


def generate_embeddings_for_entities(gpu: bool = False) -> None:
    start_time = time.time()
    entities_list = {
        "bgee_species": {
            "uri": "http://purl.uniprot.org/core/Taxon",
            "label": "species",
            "description": "species scientific names",
            "endpoint": "https://www.bgee.org/sparql/",
            "pagination": False,
            "query": """PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?uri ?label
    WHERE {
        ?uri a up:Taxon ;
            up:rank up:Species ;
            up:scientificName ?label .
    }""",
        },
        "genex:AnatomicalEntity": {
            "uri": "http://purl.org/genex#AnatomicalEntity",
            "label": "Anatomical entity",
            "description": "An anatomical entity can be an organism part (e.g. brain, blood, liver and so on) or a material anatomical entity such as a cell.",
            "endpoint": "https://www.bgee.org/sparql/",
            "pagination": False,
            "query": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX genex: <http://purl.org/genex#>
    SELECT DISTINCT ?uri ?label
    WHERE {
        ?uri a genex:AnatomicalEntity ;
            rdfs:label ?label .
    }""",
        },
        "efo:EFO_0000399": {
            "uri": "http://www.ebi.ac.uk/efo/EFO_0000399",
            "label": "developmental stage",
            "description": "A developmental stage is spatiotemporal region encompassing some part of the life cycle of an organism, e.g. blastula stage.",
            "endpoint": "https://www.bgee.org/sparql/",
            "pagination": False,
            "query": """PREFIX genex: <http://purl.org/genex#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?uri ?label {
        ?uri a <http://www.ebi.ac.uk/efo/EFO_0000399> .
        ?uri rdfs:label ?label .
    }""",
        },
        "bgee_gene": {
            "uri": "http://purl.org/net/orth#Gene",
            "label": "Gene",
            "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
            "endpoint": "https://www.bgee.org/sparql/",
            "pagination": False,
            "query": """PREFIX orth: <http://purl.org/net/orth#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dc: <http://purl.org/dc/terms/>
    SELECT DISTINCT ?uri ?label {
        ?uri a orth:Gene .
        {
            ?uri rdfs:label ?label .
        } UNION {
            ?uri dc:identifier ?label .
        }
    }""",
        },
        "oma_protein": {
            "uri": "http://purl.org/net/orth#Protein",
            "label": "Protein",
            "description": "A sequence of amino acids linked by peptide bonds which may lack appreciable tertiary structure and may not be liable to irreversible denaturation.",
            "endpoint": "https://sparql.omabrowser.org/sparql/",
            "pagination": False,
            "query": """PREFIX dc: <http://purl.org/dc/terms/>
    PREFIX orth: <http://purl.org/net/orth#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?uri ?label {
    ?uri a orth:Protein .
    {
        ?uri rdfs:label ?label .
    } UNION {
        ?uri dc:identifier ?label .}
    }""",
        },
        "oma_gene": {
            "uri": "http://purl.org/net/orth#Gene",
            "label": "Gene",
            "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
            "endpoint": "https://sparql.omabrowser.org/sparql/",
            "pagination": False,
            "query": """PREFIX orth: <http://purl.org/net/orth#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?uri ?label {
    ?uri a orth:Protein .
    ?uri rdfs:label ?label .}""",
        },
        "uniprot_species": {
            "uri": "http://purl.uniprot.org/core/Taxon",
            "label": "species",
            "description": "species scientific names",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "pagination": False,
            "query": """PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?uri ?label
    WHERE {
        ?uri a up:Taxon ;
            up:rank up:Species ;
            up:scientificName|up:commonName ?label .
    }""",
        },
        "oma_species": {
            "uri": "http://purl.uniprot.org/core/Taxon",
            "label": "species",
            "description": "species scientific names",
            "endpoint": "https://sparql.omabrowser.org/sparql/",
            "pagination": False,
            "query": """PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?uri ?label
    WHERE {
        ?uri a up:Taxon ;
            up:rank up:Species ;
            up:scientificName ?label .
    }""",
        },
        "oma_tax_levels": {
            "uri": "http://purl.org/net/orth#TaxonomicRange",
            "label": "Taxonomic level",
            "description": "The taxonomic level represents the taxon at which a group of sequences are considered members of the same cluster of orthologs/paralogs",
            "endpoint": "https://sparql.omabrowser.org/sparql/",
            "pagination": False,
            "query": """PREFIX orth: <http://purl.org/net/orth#>
        SELECT ?uri ?label
        WHERE {
            ?uri a orth:TaxonomicRange ;
                orth:taxRange  ?label .
        }""",
        },
        "uniprot_taxon": {
            "uri": "http://purl.uniprot.org/core/Taxon",
            "label": "species",
            "description": "taxon scientific names",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "pagination": False,
            "query": """PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?uri ?label
    WHERE {
        ?uri a up:Taxon ;
            up:scientificName ?label .
    }""",
        },
        "uniprot_disease": {
            "uri": "http://purl.uniprot.org/core/Disease",
            "label": "Disease",
            "description": "The preferred names of diseases.",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "pagination": False,
            "query": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?uri ?label ?type WHERE {
        ?uri a up:Disease ;
            skos:prefLabel ?label .
    }""",
        },
        # TODO: way too many UniProt genes, should we just ignore indexing genes?
        #     "uniprot_gene": {
        #         "uri": "http://purl.uniprot.org/core/Gene",
        #         "label": "Gene",
        #         "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
        #         "endpoint": "https://sparql.uniprot.org/sparql/",
        #         "pagination": True,
        #         "query": """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        # PREFIX up: <http://purl.uniprot.org/core/>
        # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        # SELECT  ?uri ?label {
        # ?uri a up:Gene .
        # ?uri skos:prefLabel ?label .}""",
        #     },
        #     "uniprot_protein": {
        #         "uri": "http://purl.uniprot.org/core/Protein",
        #         "label": "Protein",
        #         "description": "A sequence of amino acids linked by peptide bonds which may lack appreciable tertiary structure and may not be liable to irreversible denaturation.",
        #         "endpoint": "https://sparql.uniprot.org/sparql/",
        #         "pagination": True,
        #         "query": """PREFIX up: <http://purl.uniprot.org/core/>
        # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        # SELECT  ?uri ?label {
        # ?uri a up:Protein .
        # ?uri rdfs:label ?label .}""",
        #     },
        #     "uniprot_mnemonics": {
        #         "uri": "http://purl.uniprot.org/core/Protein",
        #         "label": "mnemonic",
        #         "description": "uniprot mnemonic",
        #         "endpoint": "https://sparql.uniprot.org/sparql/",
        #         "pagination": True,
        #         "query": """PREFIX up: <http://purl.uniprot.org/core/>
        # SELECT ?uri ?label
        # WHERE {
        #     ?uri a up:Protein ;
        #         up:mnemonic  ?label .
        #     }""",
        #     },
    }

    docs: list[Document] = []
    for entity in entities_list.values():
        if entity["pagination"]:
            max_results = 200000
            pagination = (max_results, 0)
            while retrieve_index_data(entity, docs, pagination):
                pagination = (pagination[0], pagination[1] + max_results)
        else:
            retrieve_index_data(entity, docs)

    print(
        f"Done querying SPARQL endpoints in {(time.time() - start_time) / 60:.2f} minutes, generating embeddings for {len(docs)} entities..."
    )

    if qdrant_client.collection_exists(settings.entities_collection_name):
        qdrant_client.delete_collection(settings.entities_collection_name)

    # Initialize collection in Qdrant vectordb with hybrid retrieval mode (dense and sparse vectors)
    # With indexes loaded on disk to avoid OOM errors when indexing large collections
    qdrant_client.create_collection(
        collection_name=settings.entities_collection_name,
        vectors_config=models.VectorParams(
            size=settings.embedding_dimensions,
            distance=models.Distance.COSINE,
            on_disk=True,
        ),
        hnsw_config=models.HnswConfigDiff(on_disk=True),
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )

    # Process documents in batches to handle millions of entities efficiently
    embedding_model = TextEmbedding(settings.embedding_model, providers=["CUDAExecutionProvider"] if gpu else None)
    sparse_embedding_model = SparseTextEmbedding(settings.sparse_embedding_model)

    batch_size = 1000  # Adjust based on your GPU memory and document size
    total_docs = len(docs)

    for batch_start in range(0, total_docs, batch_size):
        batch_end = min(batch_start + batch_size, total_docs)
        batch_docs = docs[batch_start:batch_end]

        # Generate embeddings for this batch
        batch_texts = [doc.page_content for doc in batch_docs]
        embeddings = embedding_model.embed(batch_texts)
        sparse_embeddings = sparse_embedding_model.embed(batch_texts)

        # Prepare batch for upsert
        batch_vectors = [emb.tolist() for emb in embeddings]
        batch_sparse_vectors = [
            models.SparseVector(indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist())
            for sparse_emb in sparse_embeddings
        ]
        batch_payloads = [doc.metadata for doc in batch_docs]

        # Prepare points with both dense and sparse vectors
        points = [
            models.PointStruct(
                id=batch_start + idx + 1,
                vector={
                    "": batch_vectors[idx],
                    "sparse": batch_sparse_vectors[idx],
                },
                payload=batch_payloads[idx],
            )
            for idx in range(len(batch_docs))
        ]

        # Upsert batch to Qdrant
        qdrant_client.upsert(
            collection_name=settings.entities_collection_name,
            points=points,
        )

        # Progress reporting
        progress = (batch_end / total_docs) * 100
        elapsed = (time.time() - start_time) / 60
        print(f"Progress: {batch_end}/{total_docs} ({progress:.1f}%) - {elapsed:.2f} minutes elapsed")

    print(
        f"Done generating and indexing embeddings in collection {settings.entities_collection_name} for {len(docs)} entities in {(time.time() - start_time) / 60:.2f} minutes"
    )

    # Alternative: Use langchain-qdrant for indexing with hybrid retrieval
    # from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
    # vectordb = QdrantVectorStore(
    #     client=qdrant_client,
    #     # url=settings.vectordb_url,
    #     collection_name=settings.entities_collection_name,
    #     embedding=make_dense_encoder(settings.embedding_model, gpu),
    #     sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
    #     retrieval_mode=RetrievalMode.HYBRID,
    # )
    # vectordb.add_documents(docs, batch_size=64)
    # TODO: Check how much times it takes with default batch size of 64
    # vectordb.add_documents(docs, batch_size=256)
    # Done generating and indexing embeddings in collection entities for 7 960 941 entities in 204.51 minutes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true", help="Use GPU when generating the embeddings")
    args = parser.parse_args()
    generate_embeddings_for_entities(args.gpu)
