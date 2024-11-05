from langchain_core.documents import Document
from qdrant_client import models

from sparql_llm.embed import get_embedding_model, get_vectordb
from sparql_llm.utils import query_sparql
import csv


embedding_model = get_embedding_model()

entities_list = {
    "genex:AnatomicalEntity": {
        "uri": "http://purl.org/genex#AnatomicalEntity",
        "label": "Anatomical entity",
        "description": "An anatomical entity can be an organism part (e.g. brain, blood, liver and so on) or a material anatomical entity such as a cell.",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX genex: <http://purl.org/genex#>
SELECT DISTINCT ?uri ?label
WHERE {
    ?uri a genex:AnatomicalEntity ;
        rdfs:label ?label .
}"""
    },
    "bgee_species": {
        "uri": "http://purl.uniprot.org/core/Taxon",
        "label": "species",
        "description": "species scientific names",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?uri ?label
WHERE {
    ?uri a up:Taxon ;
        up:rank up:Species ;
        up:scientificName ?label .
}"""
    },
  "efo:EFO_0000399": {
        "uri": "http://www.ebi.ac.uk/efo/EFO_0000399",
        "label": "developmental stage",
        "description": "A developmental stage is spatiotemporal region encompassing some part of the life cycle of an organism, e.g. blastula stage.",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX genex: <http://purl.org/genex#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label {
  ?uri a <http://www.ebi.ac.uk/efo/EFO_0000399> .
  ?uri rdfs:label ?label .}"""
    },
  "bgee_gene": {
        "uri": "http://purl.org/net/orth#Gene",
        "label": "Gene",
        "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX orth: <http://purl.org/net/orth#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label {
  ?uri a orth:Gene .
  ?uri rdfs:label ?label .}"""
    },
    "oma_protein": {
        "uri": "http://purl.org/net/orth#Protein",
        "label": "Protein",
        "description": "A sequence of amino acids linked by peptide bonds which may lack appreciable tertiary structure and may not be liable to irreversible denaturation.",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX dc: <http://purl.org/dc/terms/>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?uri ?label {
  ?uri a orth:Protein .
  {?uri rdfs:label ?label .}
  UNION {
  ?uri dc:identifier ?label .}
}"""
    },
  "oma_gene": {
        "uri": "http://purl.org/net/orth#Gene",
        "label": "Gene",
        "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX orth: <http://purl.org/net/orth#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label {
  ?uri a orth:Protein .
  ?uri rdfs:label ?label .}"""
    },
  "uniprot_gene": {
        "uri": "http://purl.uniprot.org/core/Gene",
        "label": "Gene",
        "description": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript. A gene may include regulatory regions, transcribed regions and/or other functional sequence regions.",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label {
  ?uri a up:Gene .
  ?uri skos:prefLabel ?label .}"""
    },
  "uniprot_protein": {
        "uri": "http://purl.uniprot.org/core/Protein",
        "label": "Protein",
        "description": "A sequence of amino acids linked by peptide bonds which may lack appreciable tertiary structure and may not be liable to irreversible denaturation.",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?uri ?label {
  ?uri a up:Protein .
  ?uri rdfs:label ?label .}"""
    },
    "uniprot_species": {
        "uri": "http://purl.uniprot.org/core/Taxon",
        "label": "species",
        "description": "species scientific names",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?uri ?label
WHERE {
    ?uri a up:Taxon ;
        up:rank up:Species ;
        up:scientificName ?label .
}"""
    },
    "oma_species": {
        "uri": "http://purl.uniprot.org/core/Taxon",
        "label": "species",
        "description": "species scientific names",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?uri ?label
WHERE {
    ?uri a up:Taxon ;
        up:rank up:Species ;
        up:scientificName ?label .
}"""
    }
}

docs: list[Document] = []
for entity in entities_list.values():
    entities_res = query_sparql(entity["query"], entity["endpoint"])["results"]["bindings"]
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
print(f"Generating embeddings for {len(docs)} entities")

# To test with a smaller number of entities
# docs = docs[:10]

embeddings = embedding_model.embed([q.page_content for q in docs])

with open('entities_embeddings.csv', mode='w', newline='') as file:
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