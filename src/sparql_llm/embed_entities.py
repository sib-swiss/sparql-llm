import csv
import os
import time
from ast import literal_eval

from langchain_core.documents import Document
from qdrant_client import models

from sparql_llm.config import get_embedding_model, get_vectordb, settings
from sparql_llm.utils import query_sparql
from tqdm import tqdm

entities_embeddings_dir = os.path.join("data", "embeddings")
entities_embeddings_filepath = os.path.join(entities_embeddings_dir, "entities_embeddings.csv")

def retrieve_index_data(entity: dict, docs: list[Document], pagination: (int, int) = None):
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
                    "uri": entity_res["uri"]["value"],
                    "endpoint_url": entity["endpoint"],
                    "entity_type": entity["uri"],
                },
            )
        )
    return entities_res


def generate_embeddings_for_entities():
    start_time = time.time()
    embedding_model = get_embedding_model()

    entities_list = {
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
    ?uri rdfs:label ?label .}""",
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
        {?uri rdfs:label ?label .}
        UNION {
        ?uri dc:identifier ?label .}
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
    {?uri rdfs:label ?label .}
    UNION {
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
        "uniprot_gene": {
            "uri": "http://purl.uniprot.org/core/Gene",
            "label": "Gene",
            "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "pagination": True,
            "query": """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT  ?uri ?label {
    ?uri a up:Gene .
    ?uri skos:prefLabel ?label .}""",
        },
        "uniprot_protein": {
            "uri": "http://purl.uniprot.org/core/Protein",
            "label": "Protein",
            "description": "A sequence of amino acids linked by peptide bonds which may lack appreciable tertiary structure and may not be liable to irreversible denaturation.",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "pagination": True,
            "query": """PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT  ?uri ?label {
    ?uri a up:Protein .
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
            up:scientificName ?label .
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
        "uniprot_mnemonics": {
            "uri": "http://purl.uniprot.org/core/Protein",
            "label": "mnemonic",
            "description": "uniprot mnemonic",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "pagination": True,
            "query": """PREFIX up: <http://purl.uniprot.org/core/>
    SELECT ?uri ?label
    WHERE {
        ?uri a up:Protein ;
            up:mnemonic  ?label .
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
        ,
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
} """,
        },
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

    # entities_res = query_sparql(entity["query"], entity["endpoint"])["results"]["bindings"]
    # print(f"Found {len(entities_res)} entities for {entity['label']} in {entity['endpoint']}")

    print(f"Done querying in {time.time() - start_time} seconds, generating embeddings for {len(docs)} entities")

    # To test with a smaller number of entities
    # docs = docs[:10]

    embeddings = embedding_model.embed([q.page_content for q in docs])

    if not os.path.exists(entities_embeddings_dir):
        os.makedirs(entities_embeddings_dir)

    with open(entities_embeddings_filepath, mode="w", newline="") as file:
        writer = csv.writer(file)
        header = ["label", "uri", "endpoint_url", "entity_type", "embedding"]
        writer.writerow(header)

        for doc, embedding in zip(docs, embeddings):
            row = [
                doc.metadata["label"],
                doc.metadata["uri"],
                doc.metadata["endpoint_url"],
                doc.metadata["entity_type"],
                embedding.tolist(),
            ]
            writer.writerow(row)

    print(f"Done generating embeddings for {len(docs)} entities in {time.time() - start_time} seconds")

    # vectordb = get_vectordb()
    # vectordb.upsert(
    #     collection_name="entities",
    #     points=models.Batch(
    #         ids=list(range(1, len(docs) + 1)),
    #         vectors=embeddings,
    #         payloads=[doc.metadata for doc in docs],
    #     ),
    #     # wait=False, # Waiting for indexing to finish or not
    # )


def load_entities_embeddings_to_vectordb():
    start_time = time.time()
    vectordb = get_vectordb()
    docs = []
    embeddings = []

    print("Reading entities embeddings from the .csv file")
    with open(entities_embeddings_filepath) as file:
        reader = csv.DictReader(file)
        for row in tqdm(reader, desc="Extracting embeddings from CSV file"):
            docs.append(
                Document(
                    page_content=row["label"],
                    metadata={
                        "label": row["label"],
                        "uri": row["uri"],
                        "endpoint_url": row["endpoint_url"],
                        "entity_type": row["entity_type"],
                    },
                )
            )
            embeddings.append(literal_eval(row["embedding"]))
    print(f"Found embeddings for {len(docs)} entities in {time.time() - start_time} seconds. Now adding them to the vectordb")
    vectordb.upsert(
        collection_name=settings.entities_collection_name,
        points=models.Batch(
            ids=list(range(1, len(docs) + 1)),
            vectors=embeddings,
            payloads=[doc.metadata for doc in docs],
        ),
    )

    print(f"Done uploading embeddings for {len(docs)} entities in the vectordb in {time.time() - start_time} seconds")


if __name__ == "__main__":
    generate_embeddings_for_entities()
