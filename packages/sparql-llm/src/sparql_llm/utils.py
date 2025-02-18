import json
import time
from typing import Any, Optional

import httpx
import rdflib
from curies_rs import Converter

# Prefixes utilities

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


# def get_endpoints_schema_and_prefixes(endpoints: list[str]) -> tuple["EndpointsSchemaDict", dict[str, str]]:
#     """Return a tuple of VoID descriptions and prefixes for the given endpoints."""
#     return (

#     )


def get_prefixes_for_endpoints(endpoints: list[str]) -> dict[str, str]:
    """Return a dictionary of prefixes for the given endpoints."""
    prefixes: dict[str, str] = {}
    for endpoint_url in endpoints:
        try:
            for row in query_sparql(GET_PREFIXES_QUERY, endpoint_url)["results"]["bindings"]:
                if row["namespace"]["value"] not in prefixes.values():
                    prefixes[row["prefix"]["value"]] = row["namespace"]["value"]
        except Exception as e:
            print(f"Error retrieving prefixes from {endpoint_url}: {e}")
    return prefixes


def get_prefix_converter(prefix_dict: dict[str, str]) -> Converter:
    """Return a prefix converter."""
    return Converter.from_prefix_map(json.dumps(prefix_dict))


# VoID description utilities

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
        ?linkset void:subjectsTarget [ void:class ?subjectClass ] ;
            void:linkPredicate ?prop ;
            void:objectsTarget [ void:class ?objectClass ] .
    }
}"""

# A dictionary to store triples like structure: dict[subject][predicate] = list[object]
# Also used to store VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]
SchemaDict = dict[str, dict[str, list[str]]]
# The VoidDict type, but we also store the endpoints URLs in an outer dict
EndpointsSchemaDict = dict[str, SchemaDict]


def get_schema_for_endpoint(endpoint_url: str, void_file: Optional[str] = None) -> SchemaDict:
    """Get a dict of VoID description of a SPARQL endpoint directly from the endpoint or from a VoID description URL.

    Formatted as: dict[subject_cls][predicate] = list[object_cls/datatype]"""
    void_dict: SchemaDict = {}
    try:
        if void_file:
            g = rdflib.Graph()
            if void_file.startswith(("http://", "https://")):
                # Handle URL case
                with httpx.Client() as client:
                    for attempt in range(10):
                        # Retry a few times in case of HTTP errors, e.g. https://sparql.uniprot.org/.well-known/void/
                        try:
                            resp = client.get(void_file, headers={"Accept": "text/turtle"}, follow_redirects=True)
                            resp.raise_for_status()
                            if resp.text.strip() == "":
                                raise ValueError(f"Empty response for VoID description from {void_file}")
                            g.parse(data=resp.text, format="turtle")
                            break
                        except Exception as e:
                            if attempt == 3:
                                raise e
                            time.sleep(1)
                            continue
            else:
                # Handle local file case
                g.parse(void_file, format="turtle")
            results = g.query(GET_VOID_DESC)
            bindings = [{str(k): {"value": str(v)} for k, v in row.asdict().items()} for row in results]
        else:
            bindings = query_sparql(GET_VOID_DESC, endpoint_url)["results"]["bindings"]

        for void_triple in bindings:
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
            raise Exception("No VoID description found")
    except Exception as e:
        print(f"Could not retrieve VoID description from {void_file if void_file else endpoint_url}: {e}")
    return void_dict


def query_sparql(
    query: str,
    endpoint_url: str,
    post: bool = False,
    timeout: Optional[int] = None,
    client: Optional[httpx.Client] = None,
) -> Any:
    """Execute a SPARQL query on a SPARQL endpoint using httpx"""
    should_close = False
    if client is None:
        client = httpx.Client(
            follow_redirects=True, headers={"Accept": "application/sparql-results+json"}, timeout=timeout
        )
        should_close = True

    try:
        if post:
            resp = client.post(
                endpoint_url,
                data={"query": query},
            )
        else:
            # NOTE: We prefer GET because in the past it seemed like some endpoints at the SIB were having issues with POST
            # But not sure if this is still the case
            resp = client.get(
                endpoint_url,
                params={"query": query},
            )
        resp.raise_for_status()
        return resp.json()
    finally:
        if should_close:
            client.close()
