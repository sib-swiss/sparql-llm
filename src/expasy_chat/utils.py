import json

from curies_rs import Converter
from rdflib import Graph
from rdflib.plugins.stores.sparqlstore import SPARQLStore
from SPARQLWrapper import SPARQLWrapper

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


def get_prefixes_for_endpoints(endpoints: list[str]) -> dict[str, str]:
    """Return a dictionary of prefixes for the given endpoints."""
    prefixes = {}
    for endpoint_url in endpoints:
        g = Graph(SPARQLStore(endpoint_url), bind_namespaces="none")
        for row in g.query(GET_PREFIXES_QUERY):
            if str(row.namespace) not in prefixes.values():
                prefixes[str(row.prefix)] = str(row.namespace)
    return prefixes


def get_prefix_converter(prefix_dict: dict[str, str]) -> Converter:
    """Return a prefix converter."""
    return Converter.from_prefix_map(json.dumps(prefix_dict))


GET_VOID_DESC = """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX void: <http://rdfs.org/ns/void#>
PREFIX void-ext: <http://ldf.fi/void-ext#>
SELECT DISTINCT ?class1 ?prop ?class2 ?datatype
WHERE {
    ?cp void:class ?class1 ;
        void:propertyPartition ?pp .
    ?pp void:property ?prop .
    OPTIONAL {
        {
            ?pp  void:classPartition [ void:class ?class2 ] .
        } UNION {
            ?pp void-ext:datatypePartition [ void-ext:datatype ?datatype ] .
        }
    }
}"""


def get_void_dict(endpoint_url: str) -> dict[str, dict[str, list[str]]]:
    """Get a dict of VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]"""
    sparql_endpoint = SPARQLWrapper(endpoint_url)
    sparql_endpoint.setQuery(GET_VOID_DESC)
    sparql_endpoint.setReturnFormat("json")
    void_dict = {}
    try:
        void_res = sparql_endpoint.query().convert()
        for void_triple in void_res["results"]["bindings"]:
            if void_triple["class1"]["value"] not in void_dict:
                void_dict[void_triple["class1"]["value"]] = {}
            if void_triple["prop"]["value"] not in void_dict[void_triple["class1"]["value"]]:
                void_dict[void_triple["class1"]["value"]][void_triple["prop"]["value"]] = []
            if "class2" in void_triple:
                void_dict[void_triple["class1"]["value"]][void_triple["prop"]["value"]].append(
                    void_triple["class2"]["value"]
                )
            if "datatype" in void_triple:
                void_dict[void_triple["class1"]["value"]][void_triple["prop"]["value"]].append(
                    void_triple["datatype"]["value"]
                )
        if len(void_dict) == 0:
            raise Exception("No VoID description found in the endpoint")
    except Exception as e:
        print(f"Could not retrieve VoID description for endpoint {endpoint_url}: {e}")
    return void_dict


# def query_sparql(query: str, endpoint_url: str) -> dict:
#     """Execute a SPARQL query on a SPARQL endpoint using requests"""
#     # g = Graph(SPARQLStore(endpoint_url))
#     # # g = Graph(store, identifier=None, bind_namespaces="none", method="POST")
#     # return g.query(query)
#     resp = requests.post(
#         endpoint_url,
#         headers={
#             "Accept": "application/sparql-results+json",
#             # "User-agent": "sparqlwrapper 2.0.1a0 (rdflib.github.io/sparqlwrapper)"
#         },
#         json={"query": query},
#         timeout=60,
#     )
#     resp.raise_for_status()
#     return resp.json()
