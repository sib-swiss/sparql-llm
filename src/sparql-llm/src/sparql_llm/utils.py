import json
import logging
from typing import Any, Optional, TypedDict

import httpx
import rdflib
from curies_rs import Converter

# Disable logger in your code with logging.getLogger("sparql_llm").setLevel(logging.WARNING)
logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
# formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
# handler.setFormatter(formatter)
logger.addHandler(handler)


class SparqlEndpointLinks(TypedDict, total=False):
    """A dictionary to store links and filepaths about a SPARQL endpoint."""

    endpoint_url: str
    void_file: Optional[str]
    examples_file: Optional[str]
    homepage_url: Optional[str]
    label: Optional[str]
    description: Optional[str]
    # ontology_url: Optional[str]


# Prefixes utilities

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


def get_prefixes_and_schema_for_endpoints(
    endpoints: list[SparqlEndpointLinks],
) -> tuple[dict[str, str], "EndpointsSchemaDict"]:
    """Return a dictionary of prefixes and a dictionary of VoID classes schema for the given endpoints."""
    prefixes_map: dict[str, str] = {}
    endpoints_void_dict: EndpointsSchemaDict = {}
    for endpoint in endpoints:
        endpoints_void_dict[endpoint["endpoint_url"]] = get_schema_for_endpoint(
            endpoint["endpoint_url"], endpoint.get("void_file")
        )
        prefixes_map = get_prefixes_for_endpoint(endpoint["endpoint_url"], endpoint.get("examples_file"), prefixes_map)
    return prefixes_map, endpoints_void_dict


def get_prefixes_for_endpoint(
    endpoint_url: str, examples_file: Optional[str] = None, prefixes_map: Optional[dict[str, str]] = None
) -> dict[str, str]:
    """Return a dictionary of prefixes for the given endpoint."""
    if prefixes_map is None:
        prefixes_map = {}
    try:
        for row in query_sparql(GET_PREFIXES_QUERY, endpoint_url, use_file=examples_file)["results"]["bindings"]:
            if row["namespace"]["value"] not in prefixes_map.values():
                prefixes_map[row["prefix"]["value"]] = row["namespace"]["value"]
    except Exception as e:
        logger.warning(f"Error retrieving prefixes for {endpoint_url}: {e}")
    return prefixes_map


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

SchemaDict = dict[str, dict[str, list[str]]]
"""A dictionary to store the classes schema of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]"""
EndpointsSchemaDict = dict[str, SchemaDict]
"""A dictionary to store the classes schema of multiple endpoints: dict[endpoint_url][subject_cls][predicate] = list[object_cls/datatype]"""


def get_schema_for_endpoint(endpoint_url: str, void_file: Optional[str] = None) -> SchemaDict:
    """Get a dict of VoID description of a SPARQL endpoint directly from the endpoint or from a VoID description URL.

    Formatted as: dict[subject_cls][predicate] = list[object_cls/datatype]"""
    void_dict: SchemaDict = {}
    try:
        # if void_file:
        #     g = rdflib.Graph()
        #     if void_file.startswith(("http://", "https://")):
        #         # Handle URL case
        #         with httpx.Client() as client:
        #             for attempt in range(10):
        #                 # Retry a few times in case of HTTP errors, e.g. https://sparql.uniprot.org/.well-known/void/
        #                 try:
        #                     resp = client.get(void_file, headers={"Accept": "text/turtle"}, follow_redirects=True)
        #                     resp.raise_for_status()
        #                     if resp.text.strip() == "":
        #                         raise ValueError(f"Empty response for VoID description from {void_file}")
        #                     g.parse(data=resp.text, format="turtle")
        #                     break
        #                 except Exception as e:
        #                     if attempt == 3:
        #                         raise e
        #                     time.sleep(1)
        #                     continue
        #     else:
        #         # Handle local file case
        #         g.parse(void_file, format="turtle")
        #     results = g.query(GET_VOID_DESC)
        #     bindings = [{str(k): {"value": str(v)} for k, v in row.asdict().items()} for row in results]
        # else:
        #     bindings = query_sparql(GET_VOID_DESC, endpoint_url)["results"]["bindings"]

        for void_triple in query_sparql(GET_VOID_DESC, endpoint_url, use_file=void_file)["results"]["bindings"]:
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
        logger.warning(f"Could not retrieve VoID description from {void_file if void_file else endpoint_url}: {e}")
    return void_dict

# TODO: use SPARQLWrapper
# sparqlw = SPARQLWrapper(endpoint)
# sparqlw.setReturnFormat(JSON)
# sparqlw.setOnlyConneg(True)
# sparqlw.setQuery(query)
# res = sparqlw.query().convert()
def query_sparql(
    query: str,
    endpoint_url: str,
    post: bool = False,
    timeout: Optional[int] = None,
    client: Optional[httpx.Client] = None,
    use_file: Optional[str] = None,
    check_service_desc: bool = True,
) -> Any:
    """Execute a SPARQL query on a SPARQL endpoint or its service description using httpx or a RDF turtle file using rdflib."""
    if use_file:
        g = rdflib.Graph()
        g.parse(use_file, format="turtle")
        results = g.query(query)
        return {
            "results": {"bindings": [{str(k): {"value": str(v)} for k, v in row.asdict().items()} for row in results]}
        }
    else:
        should_close = False
        if client is None:
            client = httpx.Client(follow_redirects=True, timeout=timeout)
            should_close = True
        try:
            if post:
                resp = client.post(
                    endpoint_url,
                    headers={"Accept": "application/sparql-results+json"},
                    data={"query": query},
                )
            else:
                resp = client.get(
                    endpoint_url,
                    headers={"Accept": "application/sparql-results+json"},
                    params={"query": query},
                )
            resp.raise_for_status()
            resp_json = resp.json()
            if check_service_desc and not resp_json.get("results", {}).get("bindings", []):
                # If no results found directly in the endpoint we check in its service description
                resp = client.get(
                    endpoint_url,
                    headers={"Accept": "text/turtle"},
                )
                resp.raise_for_status()
                g = rdflib.Graph()
                g.parse(data=resp.text, format="turtle")
                results = g.query(query)
                bindings = []
                for row in results:
                    if hasattr(row, "asdict"):
                        bindings.append({str(k): {"value": str(v)} for k, v in row.asdict().items()})
                    elif isinstance(row, bool):
                        bindings.append({"ask-variable": {"value": str(row).lower()}})
                    else:
                        # Handle tuple results
                        bindings.append({str(var): {"value": str(val)} for var, val in zip(results.vars, row)})
                return {
                    "results": {
                        "bindings": bindings
                    }
                }
            return resp_json
        finally:
            if should_close:
                client.close()
