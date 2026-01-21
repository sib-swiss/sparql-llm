import json
import logging
from pathlib import Path
from typing import Any

import curies
import httpx
import rdflib

from sparql_llm.config import SparqlEndpointLinks, settings

# Disable logger in your code with logging.getLogger("sparql_llm").setLevel(logging.WARNING)
logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)
# handler = logging.StreamHandler()
# formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
# handler.setFormatter(formatter)
# logger.addHandler(handler)
# logger.propagate = False

logging.getLogger("httpx").setLevel(logging.WARNING)


# Prefixes utilities

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""

ENDPOINTS_METADATA_FILE = Path("data") / "endpoints_metadata.json"


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


# Use https://github.com/lu-pl/sparqlx ?
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


class EndpointsMetadataManager:
    """Lazy-loading manager for endpoints metadata."""

    def __init__(self, endpoints: list[SparqlEndpointLinks], auto_init: bool = True) -> None:
        self._endpoints = endpoints
        self._prefixes_map: dict[str, str] = {}
        self._void_dict: EndpointsSchemaDict = {}
        self._initialized = False
        if auto_init:
            self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        """Load metadata if not already loaded."""
        if self._initialized:
            return
        # Try loading from file first
        try:
            with open(ENDPOINTS_METADATA_FILE) as f:
                data = json.load(f)
                self._prefixes_map = data.get("prefixes_map", {})
                self._void_dict = data.get("classes_schema", {})
                if self._prefixes_map and self._void_dict:
                    logger.info(
                        f"💾 Loaded endpoints metadata from {ENDPOINTS_METADATA_FILE.resolve()} "
                        f"for {len(self._void_dict)} endpoints"
                    )
                    self._initialized = True
                    return
        except Exception as e:
            logger.debug(f"Could not load metadata from {ENDPOINTS_METADATA_FILE}: {e}")

        logger.info(f"Fetching metadata for {len(self._endpoints)} endpoints...")
        for endpoint in self._endpoints:
            self._void_dict[endpoint["endpoint_url"]] = get_schema_for_endpoint(
                endpoint["endpoint_url"], endpoint.get("void_file")
            )
            logger.info(f"Fetching {endpoint['endpoint_url']} metadata...")
            self._prefixes_map = get_prefixes_for_endpoint(
                endpoint["endpoint_url"], endpoint.get("examples_file"), self._prefixes_map
            )
        # Cache to JSON file
        with open(ENDPOINTS_METADATA_FILE, "w") as f:
            json.dump({"prefixes_map": self._prefixes_map, "classes_schema": self._void_dict}, f, indent=2)
        self._initialized = True
        logger.info(f"💾 Cached endpoints metadata to {ENDPOINTS_METADATA_FILE.resolve()}")

    @property
    def prefixes_map(self) -> dict[str, str]:
        """Get prefixes map, loading lazily if needed."""
        self._ensure_loaded()
        return self._prefixes_map or {}

    @property
    def void_dict(self) -> "EndpointsSchemaDict":
        """Get endpoints VoID schema dict, loading lazily if needed."""
        self._ensure_loaded()
        return self._void_dict or {}

    # def reset(self) -> None:
    #     """Reset cached metadata (useful for re-initialization after init_vectordb)."""
    #     self._prefixes_map = {}
    #     self._void_dict = {}


# Global instance, metadata loads lazily on first property access
endpoints_metadata = EndpointsMetadataManager(settings.endpoints, settings.auto_init)
