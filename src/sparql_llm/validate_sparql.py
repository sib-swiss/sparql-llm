import re
from collections import defaultdict
from typing import Any, Optional, Union

from curies_rs import Converter
from rdflib import Namespace, Variable
from rdflib.paths import AlternativePath, MulPath, Path, SequencePath
from rdflib.plugins.sparql import prepareQuery

from sparql_llm.utils import TripleDict, get_prefix_converter, get_prefixes_for_endpoints, get_void_dict

queries_pattern = re.compile(r"```sparql(.*?)```", re.DOTALL)
endpoint_pattern = re.compile(r"^#.*(https?://[^\s]+)", re.MULTILINE)


def extract_sparql_queries(md_resp: str) -> list[dict[str, Optional[str]]]:
    """Extract SPARQL queries and endpoint URL from a markdown response."""
    extracted_queries = []
    queries = queries_pattern.findall(md_resp)
    for query in queries:
        extracted_endpoint = endpoint_pattern.search(query.strip())
        extracted_queries.append(
            {
                "query": str(query).strip(),
                "endpoint_url": str(extracted_endpoint.group(1)) if extracted_endpoint else None,
            }
        )
    return extracted_queries


def add_missing_prefixes(query: str, prefixes_map: dict[str, str]) -> str:
    """Add missing prefixes to a SPARQL query."""
    # Check if the first line is a comment
    lines = query.split("\n")
    comment_line = lines[0].startswith("#") if lines else False
    # Collect prefixes to be added
    prefixes_to_add = []
    for prefix, namespace in prefixes_map.items():
        prefix_str = f"PREFIX {prefix}: <{namespace}>"
        if not re.search(prefix_str, query) and re.search(f"[(| |\u00a0|/]{prefix}:", query):
            prefixes_to_add.append(prefix_str)
            # query = f"{prefix_str}\n{query}"

    if prefixes_to_add:
        prefixes_to_add_str = "\n".join(prefixes_to_add)
        if comment_line:
            lines.insert(1, prefixes_to_add_str)
        else:
            lines.insert(0, prefixes_to_add_str)
        query = "\n".join(lines)
    return query


up = Namespace("http://purl.uniprot.org/core/")
rh = Namespace("http://rdf.rhea-db.org/")
sqc = Namespace("http://example.org/sqc/")  # SPARQL query check


# Quite simlar to the VoidDict type, but we also store the endpoints in an outer dict
SparqlTriplesDict = dict[str, TripleDict]


def sparql_query_to_dict(sparql_query: str, sparql_endpoint: str) -> SparqlTriplesDict:
    """Convert a SPARQL query string to a dictionary of triples looking like dict[endpoint][subject][predicate] = list[object]"""
    query_dict: SparqlTriplesDict = defaultdict(TripleDict)
    path_var_count = 1

    def handle_path(endpoint: str, subj: str, pred: Union[str, Path], obj: str):
        """
        Recursively handle a Path object in a SPARQL query.
        Check here to understand why we need this: https://github.com/sib-swiss/sparql-examples/blob/master/examples/UniProt/26_component_HLA_class_I_histocompatibility_domain.ttl
        """
        nonlocal path_var_count
        if isinstance(pred, MulPath):
            handle_path(endpoint, subj, pred.path, obj)
        elif isinstance(pred, SequencePath):
            # Creating variables for each step in the path
            for i_path, path_pred in enumerate(pred.args):
                path_var_count += 1
                if subj not in query_dict[endpoint]:
                    query_dict[endpoint][subj] = defaultdict(list[str])
                if i_path < len(pred.args) - 1:
                    path_var_str = f"?pathVar{path_var_count}"
                    handle_path(endpoint, subj, path_pred, path_var_str)
                    subj = path_var_str
                else:
                    handle_path(endpoint, subj, path_pred, obj)
        elif isinstance(pred, AlternativePath):
            # We just create a different triple for each alternative like they are separate paths
            for path_pred in pred.args:
                handle_path(endpoint, subj, path_pred, obj)
        else:
            # If not a path, then we got to the bottom of it, it's a URI and we can add the triple
            query_dict[endpoint][subj][str(pred)].append(obj)

    def format_var_str(var: Any) -> Any:
        """We don't want to return a str because pred might be a Path object"""
        return f"?{var}" if isinstance(var, Variable) else var

    def extract_triples(node: Any, endpoint: str):
        """Recursively go down the nodes of a SPARQL query to find triples."""
        nonlocal path_var_count
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "triples":
                    for triples in value:
                        # print(len(triples), triples)
                        # TripleBlock that can be found inside SERVICE can have multiple triples in the same list... wtf is this format
                        for i in range(0, len(triples), 3):
                            triple = triples[i : i + 3]
                            # print(triple)
                            subj: str = str(format_var_str(triple[0]))
                            pred = format_var_str(triple[1])
                            obj: str = str(format_var_str(triple[2]))
                            if subj not in query_dict[endpoint]:
                                query_dict[endpoint][subj] = defaultdict(list[str])
                            # print(pred, type(pred))
                            if isinstance(pred, Path):
                                handle_path(endpoint, subj, pred, obj)
                            else:
                                query_dict[endpoint][subj][str(pred)].append(obj)

                # Handle SERVICE clauses
                # NOTE: recursion issue when nested SERVICE clauses: https://github.com/RDFLib/rdflib/issues/2136
                elif key == "graph" and hasattr(node, "term"):
                    extract_triples(value, node.term)
                else:
                    extract_triples(value, endpoint)
        elif isinstance(node, list):
            for item in node:
                extract_triples(item, endpoint)

    extract_triples(prepareQuery(sparql_query).algebra, sparql_endpoint)
    return query_dict


def validate_sparql_with_void(query: str, endpoint_url: str, prefix_converter: Optional[Converter] = None) -> set[str]:
    """Validate SPARQL query using the VoID description of endpoints. Raise exception if errors found."""
    if prefix_converter is None:
        prefix_converter = get_prefix_converter(get_prefixes_for_endpoints([endpoint_url]))

    def validate_triple_pattern(
        subj: str,
        subj_dict: TripleDict,
        void_dict: TripleDict,
        endpoint: str,
        issues: set[str],
        parent_type: Optional[str] = None,
        parent_pred: Optional[str] = None,
    ) -> set[str]:
        pred_dict = subj_dict.get(subj, {})
        # Direct type provided for this entity
        if "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in pred_dict:
            for subj_type in pred_dict["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
                for pred in pred_dict:
                    if pred == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                        continue
                    if subj_type not in void_dict:
                        issues.add(
                            f"Type {prefix_converter.compress(subj_type)} for subject {subj} in endpoint {endpoint} does not exist. Available classes are: {', '.join(prefix_converter.compress_list(list(void_dict.keys())))}"
                        )
                    elif pred not in void_dict.get(subj_type, {}):
                        # TODO: also check if object type matches? (if defined, because it's not always available)
                        issues.add(
                            f"Subject {subj} with type {prefix_converter.compress(subj_type)} in endpoint {endpoint} does not support the predicate {prefix_converter.compress(pred)}. It can have the following predicates: {', '.join(prefix_converter.compress_list(list(void_dict.get(subj_type, {}).keys())))}"
                        )
                    for obj in pred_dict[pred]:
                        # Recursively validates objects that are variables
                        if obj.startswith("?"):
                            issues = validate_triple_pattern(
                                obj, subj_dict, void_dict, endpoint, issues, subj_type, pred
                            )
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
                                    issues = validate_triple_pattern(
                                        obj, subj_dict, void_dict, endpoint, issues, potential_type, pred
                                    )
                        break
                if missing_pred is not None:
                    # print(f"!!!! Subject {subj} {parent_type} {parent_pred} is not a valid {potential_types} !")
                    issues.add(
                        f"Subject {subj} in endpoint {endpoint} does not support the predicate {prefix_converter.compress(missing_pred)}. Correct predicate might be one of the following: {', '.join(prefix_converter.compress_list(list(potential_preds)))} (we inferred this variable might be of the type {prefix_converter.compress(potential_type)})"
                    )

        # TODO: when no type and no parent but more than 1 predicate is used, we could try to infer the type from the predicates
        # If too many potential type we give up, otherwise we infer
        # If the no type match the 2 predicates then it's not right

        # If no type and no parent type we just check if the predicates used can be found in the VoID description
        # We only run this if no errors found yet to avoid creating too many duplicates
        # TODO: we could improve this by generating a dict of errors, so we only push once the error for a subj/predicate
        # TODO: right now commented because up:evidence is missing in the VoID description, leading to misleading errors
        # elif len(error_msgs) == 0:
        #     all_preds = set()
        #     for pred in pred_dict:
        #         valid_pred = False
        #         for _subj_type, void_pred_dict in void_dict.items():
        #             all_preds.update(void_pred_dict.keys())
        #             if pred in void_pred_dict:
        #                 valid_pred = True
        #                 break
        #         if not valid_pred:
        #             error_msgs.add(
        #                 f"Predicate {prefix_converter.compress(pred)} used by subject {subj} in endpoint {endpoint} is not supported according to the VoID description. Here are the available predicates: {', '.join(prefix_converter.compress_list(list(all_preds)))}"
        #             )

        return issues

    query_dict = sparql_query_to_dict(query, endpoint_url)
    issues_msgs: set[str] = set()

    # Go through the query BGPs and check if they match the VoID description
    for endpoint, subj_dict in query_dict.items():
        void_dict = get_void_dict(endpoint)
        if len(void_dict) == 0:
            continue

        for subj in subj_dict:
            issues_msgs = validate_triple_pattern(subj, subj_dict, void_dict, endpoint, issues_msgs)

    return issues_msgs

    # TODO: figure out a structured way to store errors?
    # errors.add(
    #     {
    #         "endpoint": endpoint, "error_type": "type_not_found", # ??
    #         "subject": subj, "type": subj_type, "inferred_type": "",
    #         "wrong_type": "", "available_types": list(void_dict.keys()),
    #         "wrong_predicate": "", "available_predicates": list(void_dict.keys()),
    #         "message": f"Type {prefix_converter.compress(subj_type)} for subject {subj} in endpoint {endpoint} does not exist. Available classes are: {', '.join(prefix_converter.compress_list(list(void_dict.keys())))}"
    #     }
    # )


# @dataclass
# class QueryIssue:
#     endpoint: str
#     error_type: str
#     subject: str
#     inferred_type: str
#     wrong_class: str
#     wrong_predicate: str
#     available_options: list[str]
#     message: str
