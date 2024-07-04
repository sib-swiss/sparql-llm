import json
import re
import gc
import os
from sys import prefix

import requests
from bs4 import BeautifulSoup
from fastembed import TextEmbedding
from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
)
from rdflib import RDF, ConjunctiveGraph, Namespace


# https://qdrant.github.io/fastembed/examples/Supported_Models/
# TextEmbedding.list_supported_models()
def get_embedding_model() -> TextEmbedding:
    return TextEmbedding("BAAI/bge-large-en-v1.5")

embedding_dimensions = 1024

ONTOLOGY_CHUNK_SIZE = 3000
ONTOLOGY_CHUNK_OVERLAP = 200
# ONTOLOGY_CHUNK_SIZE = 6000
# ONTOLOGY_CHUNK_OVERLAP = 200

DEFAULT_VECTORDB_HOST = os.getenv("VECTORDB_HOST", "10.89.0.2")
# DEFAULT_VECTORDB_HOST = "10.89.0.2"

def get_vectordb(host=DEFAULT_VECTORDB_HOST) -> QdrantClient:
    return QdrantClient(
        host=host,
        prefer_grpc=True,
    )

ALL_PREFIXES_FILEPATH = "all_prefixes.json"

DOCS_COLLECTION = "expasy"

endpoints = [
    {
        "label": "UniProt",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "homepage": "https://www.uniprot.org/",
        "ontology": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/rdf/core.owl",
    },
    {
        "label": "Bgee",
        "endpoint": "https://www.bgee.org/sparql/",
        "homepage": "https://www.bgee.org/",
        "ontology": "http://purl.org/genex",
    },
    {
        "label": "Orthology MAtrix (OMA)",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "homepage": "https://omabrowser.org/",
        "ontology": "http://purl.org/net/orth",
    },
    {
        "label": "Rhea",
        "endpoint": "https://sparql.rhea-db.org/sparql/",
        "homepage": "https://www.rhea-db.org/",
    },
    {
        "label": "MetaNetx",
        "endpoint": "https://rdf.metanetx.org/sparql/",
        "homepage": "https://www.metanetx.org/",
    },
    {
        "label": "SwissLipids",
        "endpoint": "https://beta.sparql.swisslipids.org/",
        "homepage": "https://www.swisslipids.org",
    },
    {
        "label": "HAMAP",
        "endpoint": "https://hamap.expasy.org/sparql/",
        "homepage": "https://hamap.expasy.org/",
    },
    {
        "label": "NextProt",
        # "endpoint": "https://api.nextprot.org/sparql",
        "endpoint": "https://sparql.nextprot.org",
        "homepage": "https://www.nextprot.org/",
    },
    {
        "label": "OrthoDB",
        # "endpoint": "https://api.nextprot.org/sparql",
        "endpoint": "https://sparql.orthodb.org/sparql/",
        "homepage": "https://www.orthodb.org/",
    },
    # {
    #     "label": "GlyConnect",
    #     "endpoint": "https://glyconnect.expasy.org/sparql",
    #     "homepage": "https://glyconnect.expasy.org/",
    # },
    # https://enpkg.commons-lab.org/graphdb/sparql (query examnple in saved queries, check with Marco)
    # https://enpkg.commons-lab.org/graphdb/repositories/ENPKG
]


get_queries = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?comment ?query
WHERE
{
    ?sq a sh:SPARQLExecutable ;
        rdfs:label|rdfs:comment ?comment ;
        sh:select|sh:ask|sh:construct|sh:describe ?query .
} ORDER BY ?sq"""

get_prefixes = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


SCHEMA = Namespace("http://schema.org/")

def remove_a_tags(html_text: str) -> str:
    """Remove all <a> tags from the queries descriptions"""
    soup = BeautifulSoup(html_text, "html.parser")
    for a_tag in soup.find_all("a"):
        a_tag.replace_with(a_tag.text)
    return soup.get_text()


def query_sparql(query: str, endpoint: str) -> dict:
    """Execute a SPARQL query on a SPARQL endpoint using requests"""
    resp = requests.get(
        endpoint,
        headers={
            "Accept": "application/sparql-results+json",
            # "User-agent": "sparqlwrapper 2.0.1a0 (rdflib.github.io/sparqlwrapper)"
        },
        params={
            "query": query
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()

def get_example_queries(endpoint: dict[str, str]) -> list[dict]:
    """Retrieve example SPARQL queries from a SPARQL endpoint"""
    queries = []
    endpoint_name = endpoint["label"]
    endpoint_url = endpoint["endpoint"]
    try:
        # Add SPARQL queries examples to the vectordb
        results = query_sparql(get_prefixes, endpoint_url)
        prefix_map = {}
        for row in results["results"]["bindings"]:
            prefix_map[row["prefix"]["value"]] = row["namespace"]["value"]

        results = query_sparql(get_queries, endpoint_url)
        print(f"Found {len(results['results']['bindings'])} examples queries for {endpoint_url}")

        for row in results["results"]["bindings"]:
            query = row["query"]["value"]
            # Add prefixes to queries
            for prefix, namespace in prefix_map.items():
                prefix_str = f"PREFIX {prefix}: <{namespace}>"
                if not re.search(prefix_str, query) and re.search(f"[(| |\u00a0|/]{prefix}:", query):
                    query = f"{prefix_str}\n{query}"
            queries.append(
                {
                    "endpoint": endpoint_url,
                    "question": f"{endpoint_name}: {remove_a_tags(row['comment']['value'])}",
                    "answer": f"```sparql\n{query}\n```",
                    "doc_type": "sparql",
                }
            )
    except Exception as e:
        print(f"Error while fetching queries from {endpoint_name}: {e}")
    return queries, prefix_map


def get_schemaorg_description(endpoint: dict[str, str]) -> list[dict]:
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
            timeout=10
        )
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch the webpage: {resp.status_code}")
        # print(resp.text)

        # Parse HTML and find the JSON-LD script tag
        soup = BeautifulSoup(resp.content, "html.parser")
        json_ld_tags = soup.find_all("script", type="application/ld+json")
        if not json_ld_tags:
            raise Exception("No JSON-LD script tags found")

        g = ConjunctiveGraph()
        for json_ld_tag in json_ld_tags:
            json_ld_content = json_ld_tag.string
            if json_ld_content:
                g.parse(data=json_ld_content, format="json-ld")
                # json_ld_content = json.loads(json_ld_content)
                docs.append({
                    "endpoint": endpoint["endpoint"],
                    "question": f"What are the general metadata about {endpoint['label']} resource? (description, creators, license, dates, version, etc)",
                    "answer": json_ld_content,
                    "doc_type": "schemaorg_jsonld",
                })

        # Concat all schema:description of all classes in the graph
        descs = set()
        # print(len(g))
        # print(g.serialize(format="turtle"))
        for s, _p, _o in g.triples((None, RDF.type, None)):
            for _sd, _pd, desc in g.triples((s, SCHEMA.description, None)):
                descs.add(str(desc))

        if len(descs) == 0:
            raise Exception("No schema:description found in the JSON-LD script tag")
        docs.append(
            {
                "endpoint": endpoint["endpoint"],
                "question": f"What is the SIB resource {endpoint['label']} about?",
                "answer": "\n".join(descs),
                "doc_type": "schemaorg_description",
            }
        )
        # print("\n".join(descs))
    except Exception as e:
        print(f"Error while fetching schema.org metadata from {endpoint['homepage']}: {e}")
    return docs

def get_ontology(endpoint: dict[str, str]) -> list[dict]:
    if "ontology" not in endpoint:
        return []
    # g = ConjunctiveGraph(store="Oxigraph")
    g = ConjunctiveGraph()
    if endpoint["label"] == "UniProt":
        g.parse(endpoint["ontology"], format="xml")
    else:
        g.parse(endpoint["ontology"], format="ttl")
    # try:
    #     g.parse(endpoint["ontology"], format="ttl")
    # except Exception as e:
    #     g.parse(endpoint["ontology"], format="xml")

    # Chunking the ontology is done here
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=ONTOLOGY_CHUNK_SIZE, chunk_overlap=ONTOLOGY_CHUNK_OVERLAP)
    splits = text_splitter.create_documents([g.serialize(format="ttl")])

    docs = [
        {
            "endpoint": endpoint["endpoint"],
            "question": split.page_content,
            "answer": "",
            "doc_type": "ontology",
        } for split in splits
    ]
    print(f"Extracted {len(docs)} chunks for {endpoint['label']} ontology")
    return docs


def init_vectordb(vectordb_host: str = DEFAULT_VECTORDB_HOST) -> None:
    """Initialize the vectordb with example queries and ontology descriptions from the SPARQL endpoints"""
    vectordb = get_vectordb(vectordb_host)
    embedding_model = get_embedding_model()
    docs = []
    all_prefixes = {}
    for endpoint in endpoints:
        # print(endpoint["label"])
        qdocs, prefix_map = get_example_queries(endpoint)
        docs += qdocs
        all_prefixes = {**all_prefixes, **prefix_map}
        docs += get_schemaorg_description(endpoint)
        docs += get_ontology(endpoint)

    with open(ALL_PREFIXES_FILEPATH, "w") as f:
        json.dump(all_prefixes, f)

    # NOTE: Manually add infos for UniProt since we cant retrieve it for now. Taken from https://www.uniprot.org/help/about
    docs.append(
        {
            "endpoint":"https://sparql.uniprot.org/sparql/",
            "question": "What is the SIB resource UniProt about?",
            "answer": """The Universal Protein Resource (UniProt) is a comprehensive resource for protein sequence and annotation data. The UniProt databases are the UniProt Knowledgebase (UniProtKB), the UniProt Reference Clusters (UniRef), and the UniProt Archive (UniParc). The UniProt consortium and host institutions EMBL-EBI, SIB and PIR are committed to the long-term preservation of the UniProt databases.

UniProt is a collaboration between the European Bioinformatics Institute (EMBL-EBI), the SIB Swiss Institute of Bioinformatics and the Protein Information Resource (PIR). Across the three institutes more than 100 people are involved through different tasks such as database curation, software development and support.

EMBL-EBI and SIB together used to produce Swiss-Prot and TrEMBL, while PIR produced the Protein Sequence Database (PIR-PSD). These two data sets coexisted with different protein sequence coverage and annotation priorities. TrEMBL (Translated EMBL Nucleotide Sequence Data Library) was originally created because sequence data was being generated at a pace that exceeded Swiss-Prot's ability to keep up. Meanwhile, PIR maintained the PIR-PSD and related databases, including iProClass, a database of protein sequences and curated families. In 2002 the three institutes decided to pool their resources and expertise and formed the UniProt consortium.

The UniProt consortium is headed by Alex Bateman, Alan Bridge and Cathy Wu, supported by key staff, and receives valuable input from an independent Scientific Advisory Board.
""",
            "doc_type": "schemaorg_description",
        }
    )

    if not vectordb.collection_exists(DOCS_COLLECTION):
        vectordb.create_collection(
            collection_name=DOCS_COLLECTION,
            vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE),
        )

    questions = [q["question"] for q in docs]
    output = embedding_model.embed(questions)
    print(f"Done generating embeddings for {len(questions)} documents")

    vectordb.upsert(
        collection_name=DOCS_COLLECTION,
        points=models.Batch(
            ids=list(range(1, len(docs) + 1)),
            vectors=[embeddings.tolist() for embeddings in output],
            payloads=docs,
        ),
    )
    print("Done inserting documents into the vectordb")

if __name__ == "__main__":
    init_vectordb()
    print(f"VectorDB initialized with {get_vectordb().get_collection(DOCS_COLLECTION).points_count} vectors")


## TODO: get ontology infos from the SPARQL endpoint
# For each class get the vann:example provided which is an example of the class as turtle?

# PREFIX dct: <http://purl.org/dc/terms/>
# PREFIX owl: <http://www.w3.org/2002/07/owl#>
# PREFIX up: <http://purl.uniprot.org/core/>
# PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# PREFIX rh: <http://rdf.rhea-db.org/>
# PREFIX widoco: <https://w3id.org/widoco/vocab#>
# SELECT DISTINCT *
# WHERE {
#     ?ont a owl:Ontology .
#     OPTIONAL {
#         ?ont dct:title|rdfs:label ?title .
#     }
#     OPTIONAL {
#         ?ont dct:description ?desc
#     }
#     OPTIONAL {
#         ?ont dct:abstract ?abstract
#     }
#     OPTIONAL {
#         ?ont widoco:introduction ?widocoIntro
#     }
# }



## TODO: Query to get VoID metadata from the SPARQL endpoint:
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# PREFIX sh: <http://www.w3.org/ns/shacl#>
# PREFIX void: <http://rdfs.org/ns/void#>
# SELECT DISTINCT ?class1 ?class1Label ?prop ?class2Label ?class2 ?pp1triples ?graph
# WHERE {
#     ?s <http://www.w3.org/ns/sparql-service-description#graph> ?graph .
#     ?graph void:classPartition ?cp1 .
#     ?cp1 void:class ?class1 ;
#         void:propertyPartition ?pp1 .
#     ?pp1 void:property ?prop ;
#         void:triples ?pp1triples ;
#         void:classPartition ?cp2 .
#     ?cp2 void:class ?class2 .
#     OPTIONAL{
# 	    ?class1 rdfs:label ?class1Label .
#     }
#     OPTIONAL {
#     	?class2 rdfs:label ?class2Label .
#     }
# #    ?graph void:classPartition ?cp3 .
# #    ?cp3 void:class ?class2 .
# } ORDER BY DESC(?pp1triples)


# Generate OWL ontology from VoID profile:
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# PREFIX sh: <http://www.w3.org/ns/shacl#>
# PREFIX void: <http://rdfs.org/ns/void#>
# PREFIX owl: <http://www.w3.org/2002/07/owl#>
# PREFIX void-ext: <http://ldf.fi/void-ext#>

# CONSTRUCT {
#     ?class1 a owl:Class ;
#             rdfs:label ?class1Label ;
#             rdfs:subClassOf ?superClass1 .

#     ?prop a owl:ObjectProperty ;
#           rdfs:domain ?class1 ;
#           rdfs:range ?class2 ;
#           rdfs:label ?propLabel ;
#           rdfs:subPropertyOf ?superProp .

#     ?class2 a owl:Class ;
#             rdfs:label ?class2Label ;
#             rdfs:subClassOf ?superClass2 .

#     ?graph a owl:Ontology .
# } WHERE {
#     ?s <http://www.w3.org/ns/sparql-service-description#graph> ?graph .
#     ?graph void:classPartition ?cp1 .
#     ?cp1 void:class ?class1 ;
#           void:propertyPartition ?pp1 .
#     ?pp1 void:property ?prop ;
#           void:triples ?pp1triples ;
#           void:classPartition ?cp2 .
#     ?cp2 void:class ?class2 .

#     OPTIONAL { ?class1 rdfs:label ?class1Label . }
#     OPTIONAL { ?class2 rdfs:label ?class2Label . }
#     OPTIONAL { ?prop rdfs:label ?propLabel . }

#     # These are optional, as they may not exist in the dataset
#     OPTIONAL { ?class1 rdfs:subClassOf ?superClass1 . }
#     OPTIONAL { ?prop rdfs:subPropertyOf ?superProp . }
#     OPTIONAL { ?class2 rdfs:subClassOf ?superClass2 . }
# } ORDER BY DESC(?pp1triples)


# TODO: get datatypes
# PREFIX up: <http://purl.uniprot.org/core/>
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# PREFIX sh: <http://www.w3.org/ns/shacl#>
# PREFIX void: <http://rdfs.org/ns/void#>
# PREFIX owl: <http://www.w3.org/2002/07/owl#>
# PREFIX void-ext: <http://ldf.fi/void-ext#>

# SELECT ?distinctSubjects ?class1 ?class1Label ?prop ?pp1triples ?class2 ?class2Label ?distinctObjects WHERE {
#     ?s <http://www.w3.org/ns/sparql-service-description#graph> ?graph .
#     ?graph void:classPartition ?cp1 .
#     ?cp1 void:class ?class1 ;
#           void:propertyPartition ?pp1 .
#     ?pp1 void:property ?prop ;
#           void:triples ?pp1triples ;
#           void-ext:datatypePartition ?dp .
#     ?dp void-ext:datatype ?class2 .

#     OPTIONAL { ?class1 rdfs:label ?class1Label . }
#     OPTIONAL { ?class2 rdfs:label ?class2Label . }
#     OPTIONAL { ?prop rdfs:label ?propLabel . }

#     OPTIONAL { ?class1 rdfs:comment ?class1Comment . }
#     OPTIONAL { ?class2 rdfs:comment ?class2Comment . }
#     OPTIONAL { ?prop rdfs:comment ?propComment . }
# } ORDER BY DESC(?pp1triples)






# Can we get distincts? No
# ?graph void:propertyPartition ?propertyPartition .
#     ?propertyPartition void:property ?predicate ;
#       void:classPartition [
#         void:class ?subject ;
#         void:distinctSubjects ?subjectCount ;
#       ] .

#     OPTIONAL {
#       ?propertyPartition void-ext:objectClassPartition [
#       void:class ?object ;
#       void:distinctObjects ?objectCount ;
#       ]
#     }