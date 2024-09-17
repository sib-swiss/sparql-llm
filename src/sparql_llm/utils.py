import json
from typing import Any, Optional

import requests
from curies_rs import Converter

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


def get_prefixes_for_endpoints(endpoints: list[str]) -> dict[str, str]:
    """Return a dictionary of prefixes for the given endpoints."""
    prefixes: dict[str, str] = {}
    for endpoint_url in endpoints:
        try:
            # sparql_endpoint = SPARQLWrapper(endpoint_url)
            # sparql_endpoint.setReturnFormat("json")
            # sparql_endpoint.setQuery(GET_PREFIXES_QUERY)

            for row in query_sparql(GET_PREFIXES_QUERY, endpoint_url)["results"]["bindings"]:
                if row["namespace"]["value"] not in prefixes.values():
                    prefixes[row["prefix"]["value"]] = row["namespace"]["value"]
        except Exception as e:
            print(f"Error retrieving prefixes from {endpoint_url}: {e}")
    return prefixes


def get_prefix_converter(prefix_dict: dict[str, str]) -> Converter:
    """Return a prefix converter."""
    return Converter.from_prefix_map(json.dumps(prefix_dict))


GET_VOID_DESC = """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX void: <http://rdfs.org/ns/void#>
PREFIX void-ext: <http://ldf.fi/void-ext#>
SELECT DISTINCT ?subjectClass ?prop ?objectClass ?objectDatatype
WHERE {
    {
        ?cp void:class ?subjectClass ;
            void:propertyPartition ?pp .
        ?pp void:property ?prop .
        OPTIONAL {
            {
                ?pp  void:classPartition [ void:class ?objectClass ] .
            } UNION {
                ?pp void-ext:datatypePartition [ void-ext:datatype ?objectDatatype ] .
            }
        }
    } UNION {
        ?ls void:subjectsTarget ?subjectClass ;
            void:linkPredicate ?prop ;
            void:objectsTarget ?objectClass .
    }
}"""

# A dictionary to store triples like structure: dict[subject][predicate] = list[object]
# Also used to store VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]
TripleDict = dict[str, dict[str, list[str]]]


def get_void_dict(endpoint_url: str) -> TripleDict:
    """Get a dict of VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]"""
    void_dict: TripleDict = {}
    try:
        for void_triple in query_sparql(GET_VOID_DESC, endpoint_url)["results"]["bindings"]:
            if void_triple["subjectClass"]["value"] not in void_dict:
                void_dict[void_triple["subjectClass"]["value"]] = {}
            if void_triple["prop"]["value"] not in void_dict[void_triple["subjectClass"]["value"]]:
                void_dict[void_triple["subjectClass"]["value"]][void_triple["prop"]["value"]] = []
            if "objectClass" in void_triple:
                void_dict[void_triple["subjectClass"]["value"]][void_triple["prop"]["value"]].append(
                    void_triple["objectClass"]["value"]
                )
            if "objectDatatype" in void_triple:
                void_dict[void_triple["subjectClass"]["value"]][void_triple["prop"]["value"]].append(
                    void_triple["objectDatatype"]["value"]
                )
        if len(void_dict) == 0:
            raise Exception("No VoID description found in the endpoint")
    except Exception as e:
        print(f"Could not retrieve VoID description for endpoint {endpoint_url}: {e}")
    return void_dict


def query_sparql(query: str, endpoint_url: str, post: bool = False, timeout: Optional[int] = None) -> Any:
    """Execute a SPARQL query on a SPARQL endpoint using requests"""
    if post:
        resp = requests.post(
            endpoint_url,
            headers={
                "Accept": "application/sparql-results+json",
                # "User-agent": "sparqlwrapper 2.0.1a0 (rdflib.github.io/sparqlwrapper)"
            },
            data={"query": query},
            timeout=timeout,
        )
    else:
        # NOTE: We prefer GET because in the past it seemed like some endpoints at the SIB were having issues with POST
        # But not sure if this is still the case
        resp = requests.get(
            endpoint_url,
            headers={
                "Accept": "application/sparql-results+json",
                # "User-agent": "sparqlwrapper 2.0.1a0 (rdflib.github.io/sparqlwrapper)"
            },
            params={"query": query},
            timeout=timeout,
        )
    resp.raise_for_status()
    return resp.json()
