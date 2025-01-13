"""Utility & helper functions."""

import json
from typing import Any, Optional

import requests
from curies_rs import Converter
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

# Utils for LLMs

def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    return init_chat_model(model, model_provider=provider)

def get_message_text(msg: BaseMessage) -> str:
    """Get the text content of a message."""
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()

# Utils for SPARQL endpoints

# endpoints: list[dict[str, str]] = [
#     {
#         "label": "UniProt",
#         "endpoint_url": "https://sparql.uniprot.org/sparql/",
#         "homepage": "https://www.uniprot.org/",
#         "ontology": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/rdf/core.owl",
#     },
#     {
#         "label": "Bgee",
#         "endpoint_url": "https://www.bgee.org/sparql/",
#         "homepage": "https://www.bgee.org/",
#         "ontology": "http://purl.org/genex",
#     },
#     {
#         "label": "Orthology MAtrix (OMA)",
#         "endpoint_url": "https://sparql.omabrowser.org/sparql/",
#         "homepage": "https://omabrowser.org/",
#         "ontology": "http://purl.org/net/orth",
#     },
#     {
#         "label": "HAMAP",
#         "endpoint_url": "https://hamap.expasy.org/sparql/",
#         "homepage": "https://hamap.expasy.org/",
#     },
#     {
#         "label": "dbgi",
#         "endpoint_url": "https://biosoda.unil.ch/graphdb/repositories/emi-dbgi",
#         # "homepage": "https://dbgi.eu/",
#     },
#     {
#         "label": "SwissLipids",
#         "endpoint_url": "https://beta.sparql.swisslipids.org/",
#         "homepage": "https://www.swisslipids.org",
#     },
#     # Nothing in those endpoints:
#     {
#         "label": "Rhea",
#         "endpoint_url": "https://sparql.rhea-db.org/sparql/",
#         "homepage": "https://www.rhea-db.org/",
#     },
#     # {
#     #     "label": "MetaNetx",
#     #     "endpoint_url": "https://rdf.metanetx.org/sparql/",
#     #     "homepage": "https://www.metanetx.org/",
#     # },
#     {
#         "label": "OrthoDB",
#         "endpoint_url": "https://sparql.orthodb.org/sparql/",
#         "homepage": "https://www.orthodb.org/",
#     },
#     # Error querying NExtProt
#     # {
#     #     "label": "NextProt",
#     #     # "endpoint_url": "https://api.nextprot.org/sparql",
#     #     "endpoint_url": "https://sparql.nextprot.org",
#     #     "homepage": "https://www.nextprot.org/",
#     # },
#     # {
#     #     "label": "GlyConnect",
#     #     "endpoint_url": "https://glyconnect.expasy.org/sparql",
#     #     "homepage": "https://glyconnect.expasy.org/",
#     # },
# ]
# endpoints_urls = [endpoint["endpoint_url"] for endpoint in endpoints]

# GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# SELECT DISTINCT ?prefix ?namespace
# WHERE {
#     [] sh:namespace ?namespace ;
#         sh:prefix ?prefix .
# } ORDER BY ?prefix"""



# def get_prefixes_for_endpoints() -> dict[str, str]:
#     """Return a dictionary of prefixes for the given endpoints."""
#     prefixes: dict[str, str] = {}
#     for endpoint in endpoints:
#         try:
#             for row in query_sparql(GET_PREFIXES_QUERY, endpoint["endpoint_url"])["results"]["bindings"]:
#                 if row["namespace"]["value"] not in prefixes.values():
#                     prefixes[row["prefix"]["value"]] = row["namespace"]["value"]
#         except Exception as e:
#             print(f"Error retrieving prefixes from {endpoint['endpoint_url']}: {e}")
#     return prefixes


# def get_prefix_converter(prefix_dict: dict[str, str]) -> Converter:
#     """Return a prefix converter."""
#     return Converter.from_prefix_map(json.dumps(prefix_dict))


# GET_VOID_DESC = """PREFIX up: <http://purl.uniprot.org/core/>
# PREFIX void: <http://rdfs.org/ns/void#>
# PREFIX void-ext: <http://ldf.fi/void-ext#>
# SELECT DISTINCT ?subjectClass ?prop ?objectClass ?objectDatatype
# WHERE {
#     {
#         ?cp void:class ?subjectClass ;
#             void:propertyPartition ?pp .
#         ?pp void:property ?prop .
#         OPTIONAL {
#             {
#                 ?pp  void:classPartition [ void:class ?objectClass ] .
#             } UNION {
#                 ?pp void-ext:datatypePartition [ void-ext:datatype ?objectDatatype ] .
#             }
#         }
#     } UNION {
#         ?ls void:subjectsTarget ?subjectClass ;
#             void:linkPredicate ?prop ;
#             void:objectsTarget ?objectClass .
#     }
# }"""

# # A dictionary to store triples like structure: dict[subject][predicate] = list[object]
# # Also used to store VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]
# TripleDict = dict[str, dict[str, list[str]]]


# def get_void_dict(endpoint_url: str) -> TripleDict:
#     """Get a dict of VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]."""
#     void_dict: TripleDict = {}
#     try:
#         for void_triple in query_sparql(GET_VOID_DESC, endpoint_url)["results"]["bindings"]:
#             if void_triple["subjectClass"]["value"] not in void_dict:
#                 void_dict[void_triple["subjectClass"]["value"]] = {}
#             if void_triple["prop"]["value"] not in void_dict[void_triple["subjectClass"]["value"]]:
#                 void_dict[void_triple["subjectClass"]["value"]][void_triple["prop"]["value"]] = []
#             if "objectClass" in void_triple:
#                 void_dict[void_triple["subjectClass"]["value"]][void_triple["prop"]["value"]].append(
#                     void_triple["objectClass"]["value"]
#                 )
#             if "objectDatatype" in void_triple:
#                 void_dict[void_triple["subjectClass"]["value"]][void_triple["prop"]["value"]].append(
#                     void_triple["objectDatatype"]["value"]
#                 )
#         if len(void_dict) == 0:
#             raise Exception("No VoID description found in the endpoint")
#     except Exception as e:
#         print(f"Could not retrieve VoID description for endpoint {endpoint_url}: {e}")
#     return void_dict


# def query_sparql(query: str, endpoint_url: str, post: bool = False, timeout: Optional[int] = None) -> Any:
#     """Execute a SPARQL query on a SPARQL endpoint using requests."""
#     if post:
#         resp = requests.post(
#             endpoint_url,
#             headers={
#                 "Accept": "application/sparql-results+json",
#                 # "User-agent": "sparqlwrapper 2.0.1a0 (rdflib.github.io/sparqlwrapper)"
#             },
#             data={"query": query},
#             timeout=timeout,
#         )
#     else:
#         # NOTE: We prefer GET because in the past it seemed like some endpoints at the SIB were having issues with POST
#         # But not sure if this is still the case
#         resp = requests.get(
#             endpoint_url,
#             headers={
#                 "Accept": "application/sparql-results+json",
#                 # "User-agent": "sparqlwrapper 2.0.1a0 (rdflib.github.io/sparqlwrapper)"
#             },
#             params={"query": query},
#             timeout=timeout,
#         )
#     resp.raise_for_status()
#     return resp.json()
