from langchain_core.documents import Document
from qdrant_client import models

from sparql_llm.embed import get_embedding_model, get_vectordb
from sparql_llm.utils import query_sparql
import csv


embedding_model = get_embedding_model()

entities_list = {
    "genex:AnatomicalEntity": {
        "label": "Anatomical entity",
        "uri": "http://purl.org/genex#AnatomicalEntity",
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
        "label": "Anatomical entity",
        "uri": "http://purl.uniprot.org/core/Species",
        "description": "An anatomical entity can be an organism part (e.g. brain, blood, liver and so on) or a material anatomical entity such as a cell.",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
SELECT ?uri ?label
WHERE {
    ?uri a up:Taxon ;
        up:rank up:Species ;
        up:scientificName ?label .
}"""
    },
}

docs: list[Document] = []
for entity in entities_list.values():
    res = query_sparql(entity["query"], entity["endpoint"])
    for entity_res in res["results"]["bindings"]:
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