import json
import logging
from pathlib import Path
from typing import Any, Required, TypedDict

import curies
import httpx
import rdflib

# Disable logger in your code with logging.getLogger("sparql_llm").setLevel(logging.WARNING)
logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)
# handler = logging.StreamHandler()
# formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
# handler.setFormatter(formatter)
# logger.addHandler(handler)
# logger.propagate = False

logging.getLogger("httpx").setLevel(logging.WARNING)


# Total=False to make all fields optional except those marked as Required
class SparqlEndpointLinks(TypedDict, total=False):
    """A dictionary to store links and filepaths about a SPARQL endpoint."""

    endpoint_url: Required[str]
    void_file: str | None
    examples_file: str | None
    homepage_url: str | None
    label: str | None
    description: str | None
    # ontology_url: Optional[str]


# Prefixes utilities

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""

ENDPOINTS_METADATA_FILE = Path("data") / "endpoints_metadata.json"


def load_endpoints_metadata_file() -> tuple[dict[str, str], "EndpointsSchemaDict"]:
    """Load prefixes and schema from the cached metadata file."""
    try:
        with open(ENDPOINTS_METADATA_FILE) as f:
            data = json.load(f)
            logger.info(
                f"💾 Loaded endpoints metadata from {ENDPOINTS_METADATA_FILE.resolve()} for {len(data.get('classes_schema', {}))} endpoints"
            )
            return data.get("prefixes_map", {}), data.get("classes_schema", {})
    except Exception as e:
        logger.warning(f"Could not load metadata from {ENDPOINTS_METADATA_FILE}: {e}")
        return {}, {}


def get_prefixes_and_schema_for_endpoints(
    endpoints: list[SparqlEndpointLinks],
) -> tuple[dict[str, str], "EndpointsSchemaDict"]:
    """Return a dictionary of prefixes and a dictionary of VoID classes schema for the given endpoints."""
    prefixes_map, endpoints_void_dict = load_endpoints_metadata_file()
    if prefixes_map and endpoints_void_dict:
        return prefixes_map, endpoints_void_dict
    logger.info(f"Fetching metadata for {len(endpoints)} endpoints...")
    for endpoint in endpoints:
        endpoints_void_dict[endpoint["endpoint_url"]] = get_schema_for_endpoint(
            endpoint["endpoint_url"], endpoint.get("void_file")
        )
        logger.info(f"Fetching {endpoint['endpoint_url']} metadata...")
        prefixes_map = get_prefixes_for_endpoint(endpoint["endpoint_url"], endpoint.get("examples_file"), prefixes_map)
    # Cache the metadata in a JSON file
    with open(ENDPOINTS_METADATA_FILE, "w") as f:
        json.dump({"prefixes_map": prefixes_map, "classes_schema": endpoints_void_dict}, f, indent=2)
    return prefixes_map, endpoints_void_dict


def get_prefixes_for_endpoint(
    endpoint_url: str, examples_file: str | None = None, prefixes_map: dict[str, str] | None = None
) -> dict[str, str]:
    """Return a dictionary of prefixes for the given endpoint."""
    if prefixes_map is None:
        prefixes_map = {}
    try:
        for row in query_sparql(
            GET_PREFIXES_QUERY, endpoint_url, use_file=examples_file, check_service_desc=True, timeout=10
        )["results"]["bindings"]:
            if row["namespace"]["value"] not in prefixes_map.values():
                prefixes_map[row["prefix"]["value"]] = row["namespace"]["value"]
    except Exception as e:
        logger.warning(f"Error retrieving prefixes for {endpoint_url}: {e}")
    return prefixes_map


def get_prefix_converter(prefix_dict: dict[str, str]) -> curies.Converter:
    """Return a prefix converter."""
    return curies.load_prefix_map(prefix_dict)


def compress_list(converter: curies.Converter, uris: list[str]) -> list[str]:
    """Helper function to compress a list of URIs using a curies.Converter."""
    return [converter.compress(uri, passthrough=True) for uri in uris]


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


def get_schema_for_endpoint(endpoint_url: str, void_file: str | None = None) -> SchemaDict:
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

        for void_triple in query_sparql(GET_VOID_DESC, endpoint_url, use_file=void_file, check_service_desc=True)[
            "results"
        ]["bindings"]:
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
    timeout: int | None = None,
    client: httpx.Client | None = None,
    use_file: str | None = None,
    check_service_desc: bool = False,
) -> Any:
    """Execute a SPARQL query on a SPARQL endpoint or its service description using httpx or a RDF turtle file using rdflib."""
    query_resp: dict[str, Any] = {"results": {"bindings": []}}
    if use_file:
        g = rdflib.Graph()
        g.parse(use_file, format="turtle")
        results = g.query(query)
        query_resp = {
            "results": {"bindings": [{str(k): {"value": str(v)} for k, v in row.asdict().items()} for row in results]}  # type: ignore
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
            query_resp = resp.json()
            # query_resp = resp_json
            # Handle ASK queries
            if query_resp.get("boolean") is not None:
                query_resp = {
                    "results": {"bindings": [{"ask-variable": {"value": str(query_resp["boolean"]).lower()}}]}
                }
            elif check_service_desc and not query_resp.get("results", {}).get("bindings", []):
                # If no results found directly in the endpoint we check in its service description
                logger.debug(f"No results found, checking service description for {endpoint_url}...")
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
                        bindings.append({str(k): {"value": str(v)} for k, v in row.asdict().items()})  # type: ignore
                    else:
                        # Handle tuple results
                        bindings.append(
                            {str(var): {"value": str(val)} for var, val in zip(results.vars, row, strict=False)}  # type: ignore
                        )
                query_resp = {"results": {"bindings": bindings}}
        finally:
            if should_close:
                client.close()
    return query_resp
