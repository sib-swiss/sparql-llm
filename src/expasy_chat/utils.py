import json
import re
from typing import Tuple
from unittest import result

from rdflib import ConjunctiveGraph, Namespace, URIRef, Variable
from rdflib.paths import MulPath, Path, SequencePath
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.sparql import Query
from SPARQLWrapper import SPARQLWrapper

queries_pattern = re.compile(r"```sparql(.*?)```", re.DOTALL)
endpoint_pattern = re.compile(r"^#.*(https?://[^\s]+)", re.MULTILINE)

def extract_sparql_queries(md_resp: str) -> list[dict[str, str]]:
    """Extract SPARQL queries and endpoint URL from a markdown response."""
    extracted_queries = []
    queries = queries_pattern.findall(md_resp)
    for query in queries:
        extracted_endpoint = endpoint_pattern.search(query.strip())
        extracted_queries.append({
            "query": str(query).strip(),
            "endpoint": extracted_endpoint.group(1) if extracted_endpoint else None,
        })
    return extracted_queries


up = Namespace("http://purl.uniprot.org/core/")
rh = Namespace("http://rdf.rhea-db.org/")
sqc = Namespace("http://example.org/sqc/") # SPARQL query check

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


def sparql_query_to_dict(sparql_query: str, sparql_endpoint: str) -> tuple[ConjunctiveGraph, dict]:
    """Convert a SPARQL query string to a dictionary of triples looking like dict[endpoint][subject][predicate] = list[object]"""
    parsed_query = parseQuery(sparql_query)
    translated_query: Query = translateQuery(parsed_query)
    query_dict = {}
    path_var_count = 1
    # We don't really use the graph finally, only the query_dict
    g = ConjunctiveGraph()
    g.bind("up", up)
    g.bind("rh", rh)
    g.bind("sqc", sqc)

    # Recursively check all parts of the query to find BGPs
    def process_part(part, endpoint: str):
        nonlocal path_var_count
        # print(part)
        if isinstance(part, list):
            for sub_pattern in part:
                process_part(sub_pattern, endpoint)
        if hasattr(part, "name") and (part.name == "BGP" or part.name == "TriplesBlock"):
            # if part.name == "BGP" or part.name == "TriplesBlock":
            # print(part.triples)
            for triples in part.triples:
                # print(triples)
                # print(len(triples))
                # TripleBlock can have multiple triples in the same list...
                for i in range(0, len(triples), 3):
                    triple = triples[i:i+3]
                    # print(triple)
                    # TODO: handle when paths are provided? up:annotation/up:toast
                    # Maybe reuse the code from evaluate?
                    subj, pred, obj = triple[0], triple[1], triple[2]
                    # Replace variables with resources from the sqc namespace
                    if not isinstance(pred, Path):
                        g.add((
                            sqc[str(subj)] if isinstance(subj, Variable) else subj,
                            sqc[str(pred)] if isinstance(pred, Variable) else pred,
                            sqc[str(obj)] if isinstance(obj, Variable) else obj,
                            URIRef(endpoint)
                        ))
                    if isinstance(subj, Variable):
                        subj = f"?{subj}"
                    if isinstance(pred, Variable):
                        pred = f"?{pred}"
                    if isinstance(obj, Variable):
                        obj = f"?{obj}"
                    if endpoint not in query_dict:
                        query_dict[endpoint] = {}
                    if str(subj) not in query_dict[endpoint]:
                        query_dict[endpoint][str(subj)] = {}
                    if isinstance(pred, Path):
                        # TODO: handling paths
                        if isinstance(pred, MulPath):
                            # NOTE: at the moment we can't check MulPath because in OMA the nodes don't have types
                            # And our system infer they might be orth:Protein, hence triggering an error that is not relevant
                            if str(pred.path) not in query_dict[endpoint][str(subj)]:
                                query_dict[endpoint][str(subj)][str(pred.path)] = []
                            query_dict[endpoint][str(subj)][str(pred.path)].append(str(obj))
                            continue
                        elif isinstance(pred, SequencePath):
                            # Creating variables for each step in the path
                            # print("SEQ!", pred.args)
                            for i_path, path_pred in enumerate(pred.args):
                                path_var_count += 1
                                if str(subj) not in query_dict[endpoint]:
                                    query_dict[endpoint][str(subj)] = {}
                                if i_path < len(pred.args) - 1:
                                    path_var_str = f"?pathVar{path_var_count}"
                                    query_dict[endpoint][str(subj)][str(path_pred)] = [path_var_str]
                                    subj = path_var_str
                                else:
                                    query_dict[endpoint][str(subj)][str(path_pred)] = [str(obj)]
                        continue
                    elif str(pred) not in query_dict[endpoint][str(subj)]:
                        query_dict[endpoint][str(subj)][str(pred)] = []
                    query_dict[endpoint][str(subj)][str(pred)].append(str(obj))

        if hasattr(part, "p"):
            process_part(part.p, endpoint)
        if hasattr(part, "p1"):
            process_part(part.p1, endpoint)
        if hasattr(part, "p2"):
            process_part(part.p2, endpoint)

        # Meeting a SERVICE clause
        # (can't be found in RDFLib evaluate because it's a special case,
        # they use the service_string directly with a regex)
        if hasattr(part, "graph") and hasattr(part, "service_string") and hasattr(part, "term"):
            process_part(part.graph, str(part.term))
        if hasattr(part, "where"):
            process_part(part.where, endpoint)
        if hasattr(part, "part"):
            process_part(part.part, endpoint)

    def extract_basic_graph_pattern(algebra):
        # print(algebra)
        if hasattr(algebra, "p"):
            process_part(algebra.p, sparql_endpoint)

    extract_basic_graph_pattern(translated_query.algebra)
    return g, query_dict



def validate_triple_pattern(subj, subj_dict, void_dict, endpoint, error_msgs, parent_type = None, parent_pred = None) -> set[str]:
    pred_dict = subj_dict.get(subj, {})
    # Direct type provided for this entity
    if "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in pred_dict:
        for subj_type in pred_dict["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            for pred in pred_dict:
                if pred == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                    continue
                if subj_type not in void_dict:
                    error_msgs.add(f"Type {subj_type} for subject {subj} in endpoint {endpoint} does not exist. Available classes are: {', '.join(void_dict.keys())}")
                elif pred not in void_dict.get(subj_type, {}):
                    # TODO: also check if object type matches? (if defined, because it's not always available)
                    error_msgs.add(f"Subject {subj} with type {subj_type} in endpoint {endpoint} does not support the predicate {pred} according to the VOID description. It can have the following predicates: {', '.join(void_dict.get(subj_type, {}).keys())}")
                for obj in pred_dict[pred]:
                    # Recursively validates objects that are variables
                    if obj.startswith("?"):
                        error_msgs = validate_triple_pattern(obj, subj_dict, void_dict, endpoint, error_msgs, subj_type, pred)
                # TODO: if object is a variable, we check this variable
                # We can pass the parent type to the function in case no type is defined for the child

    # No type provided directly for this entity, we check if provided predicates match one of the potential type inferred for parent type
    elif parent_type and parent_pred:
        # print(f"CHECKING subject {subj} parent type {parent_type} parent pred {parent_pred}")
        missing_pred = None
        potential_types = void_dict.get(parent_type, {}).get(parent_pred, [])
        if potential_types:
            # Get the list of preds for this subj
            # preds = [pred for pred in pred_dict.keys()]
            for potential_type in potential_types:
                # print(f"Checking if {subj} is a valid {potential_type}")
                potential_preds = void_dict.get(potential_type, {}).keys()
                # Find any predicate in pred_dict.keys() that is not in potential_preds
                missing_pred = next((pred for pred in pred_dict if pred not in potential_preds), None)
                if missing_pred is None:
                    # print(f"OK Subject {subj} is a valid inferred {potential_type}!")
                    for pred in pred_dict:
                        for obj in pred_dict[pred]:
                            # If object is variable, we try to validate it too passing the potential type we just validated
                            if obj.startswith("?"):
                                error_msgs = validate_triple_pattern(obj, subj_dict, void_dict, endpoint, error_msgs, potential_type, pred)
                    break
            if missing_pred is not None:
                # print(f"!!!! Subject {subj} {parent_type} {parent_pred} is not a valid {potential_types} !")
                error_msgs.add(f"Subject {subj} in endpoint {endpoint} does not support the predicate {missing_pred} according to the VOID description. Correct predicate might be one of the following: {', '.join(potential_preds)} (we inferred this variable might be of the type {potential_type})")

    # If no type and no parent type we just check if the predicates used can be found in the VOID description
    # We only run this if no errors found yet to avoid creating too many duplicates
    # TODO: we could improve this by generating a dict of errors, so we only push once the error for a subj/predicate
    elif len(error_msgs) == 0:
        all_preds = set()
        for pred in pred_dict:
            valid_pred = False
            for _subj_type, void_pred_dict in void_dict.items():
                all_preds.update(void_pred_dict.keys())
                if pred in void_pred_dict:
                    valid_pred = True
                    break
            if not valid_pred:
                error_msgs.add(f"Predicate {pred} used by subject {subj} in endpoint {endpoint} is not supported according to the VOID description. Here are the available predicates: {', '.join(all_preds)}")

    return error_msgs




def validate_sparql_with_void(query: str, endpoint: str) -> None:
    """Validate SPARQL query using the VOID description of endpoints."""
    _g, query_dict = sparql_query_to_dict(query, endpoint)
    error_msgs: set[str] = set()
    # error_msgs = {}

    # Go through the query BGPs and check if they match the VOID description
    for endpoint, subj_dict in query_dict.items():
        # print(endpoint)
        sparql_endpoint = SPARQLWrapper(endpoint)
        sparql_endpoint.setQuery(GET_VOID_DESC)
        sparql_endpoint.setReturnFormat("json")
        try:
            void_res = sparql_endpoint.query().convert()
            void_dict = {}
            # NOTE: Build a dict[subject_cls][predicate] = list[object_cls/datatype]
            for void_triple in void_res["results"]["bindings"]:
                if void_triple["class1"]["value"] not in void_dict:
                    void_dict[void_triple["class1"]["value"]] = {}
                if void_triple["prop"]["value"] not in void_dict[void_triple["class1"]["value"]]:
                    void_dict[void_triple["class1"]["value"]][void_triple["prop"]["value"]] = []
                if "class2" in void_triple:
                    void_dict[void_triple["class1"]["value"]][void_triple["prop"]["value"]].append(void_triple["class2"]["value"])
                if "datatype" in void_triple:
                    void_dict[void_triple["class1"]["value"]][void_triple["prop"]["value"]].append(void_triple["datatype"]["value"])
            # print(void_res["results"]["bindings"])
            if len(void_dict) == 0:
                raise("No VOID description found in the endpoint")
        except Exception as e:
            print(f"Could not retrieve VOID description for endpoint {endpoint}: {e}")
            continue

        for subj in subj_dict:
            error_msgs = validate_triple_pattern(subj, subj_dict, void_dict, endpoint, error_msgs)

    if len(error_msgs) > 0:
        raise Exception("\n".join(error_msgs))
