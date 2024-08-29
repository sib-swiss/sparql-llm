from SPARQLWrapper import SPARQLWrapper

from expasy_chat.utils import get_prefix_converter, get_prefixes_for_endpoints, get_void_dict

DEFAULT_NAMESPACES_TO_IGNORE = [
    "http://www.w3.org/ns/sparql-service-description#",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/2002/07/owl#",
    "http://rdfs.org/ns/void#",
    "http://purl.org/query/voidext#",
    "http://www.w3.org/2001/XMLSchema#",
    # "http://www.w3.org/2000/01/rdf-schema#",
]


def ignore_namespaces(ns_to_ignore: list[str], cls: str) -> bool:
    return any(cls.startswith(ns) for ns in ns_to_ignore)


def get_shex_dict_from_void(
    endpoint_url: str, prefix_map: dict[str, str] | None = None, namespaces_to_ignore: list[str] | None = None
) -> dict[str, dict[str, str]]:
    """Get a dict of shex shapes from the VoID description."""
    prefix_map = prefix_map or get_prefixes_for_endpoints([endpoint_url])
    namespaces_to_ignore = namespaces_to_ignore or DEFAULT_NAMESPACES_TO_IGNORE
    prefix_converter = get_prefix_converter(prefix_map)
    void_dict = get_void_dict(endpoint_url)
    shex_dict = {}

    for subject_cls, predicates in void_dict.items():
        if ignore_namespaces(namespaces_to_ignore, subject_cls):
            continue
        try:
            subj = prefix_converter.compress(subject_cls)
        except Exception as _e:
            subj = f"<{subject_cls}>"
        shex_dict[subject_cls] = {"shex": f"{subj} {{\n  a [ {subj} ] ;\n"}

        for predicate, object_list in predicates.items():
            try:
                pred = prefix_converter.compress(predicate)
            except Exception as _e:
                pred = f"<{predicate}>"

            compressed_obj_list = prefix_converter.compress_list(object_list, passthrough=True)
            compressed_obj_list = []
            for obj in object_list:
                try:
                    compressed_obj_list.append(prefix_converter.compress(obj))
                except Exception as _e:
                    compressed_obj_list.append(f"<{obj}>")

            if (
                len(compressed_obj_list) > 0
                and len(compressed_obj_list) < 2
                and compressed_obj_list[0].startswith("xsd:")
            ):
                shex_dict[subject_cls]["shex"] += f"  {pred} {compressed_obj_list[0]} ;\n"
            elif len(compressed_obj_list) > 0:
                shex_dict[subject_cls]["shex"] += f"  {pred} [ {' '.join(compressed_obj_list)} ] ;\n"
            else:
                shex_dict[subject_cls]["shex"] += f"  {pred} IRI ;\n"

        shex_dict[subject_cls]["shex"] = shex_dict[subject_cls]["shex"].rstrip(" ;\n") + "\n}"

    if len(shex_dict) == 0:
        return shex_dict

    # Now get labels and comments for all classes
    get_labels_query = f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT DISTINCT * WHERE {{
    ?cls a owl:Class ;
        rdfs:label ?label .
    OPTIONAL {{
        ?cls rdfs:comment ?comment .
    }}
    VALUES ?cls {{ <{"> <".join(shex_dict.keys())}> }}
}}"""
    sparql_endpoint = SPARQLWrapper(endpoint_url)
    sparql_endpoint.setQuery(get_labels_query)
    sparql_endpoint.setMethod("POST")
    sparql_endpoint.setReturnFormat("json")
    void_dict = {}
    try:
        label_res = sparql_endpoint.query().convert()
        for label_triple in label_res["results"]["bindings"]:
            cls = label_triple["cls"]["value"]
            if cls not in shex_dict:
                continue
            shex_dict[cls]["label"] = label_triple["label"]["value"]
            if "comment" in label_triple:
                # shex_dict[cls]["label"] += f": {label_triple['comment']['value']}"
                shex_dict[cls]["comment"] = label_triple["comment"]["value"]
    except Exception as e:
        print(f"Could not retrieve labels for classes in endpoint {endpoint_url}: {e}")

    return shex_dict


def get_shex_from_void(endpoint_url: str, namespaces_to_ignore: list[str] | None = None) -> str:
    """Function to build complete ShEx from VoID description with prefixes and all shapes"""
    prefix_map = get_prefixes_for_endpoints([endpoint_url])
    shex_dict = get_shex_dict_from_void(endpoint_url, prefix_map, namespaces_to_ignore)
    shex_str = ""
    for prefix, namespace in prefix_map.items():
        shex_str += f"PREFIX {prefix}: <{namespace}>\n"
    for _cls_uri, shex_shape in shex_dict.items():
        if "label" in shex_shape:
            shex_str += f"# {shex_shape['label']}\n"
        if "comment" in shex_shape:
            shex_str += f"# {shex_shape['comment']}\n"
        shex_str += shex_shape["shex"] + "\n\n"
    return shex_str


# def get_void_dict(g: Graph):
#     """Get a dict of VoID description of an endpoint: dict[subject_cls][predicate] = list[object_cls/datatype]"""
#     # g = Graph(SPARQLStore(endpoint_url, auth=endpoint_auth), bind_namespaces="none")
#     # sparql_endpoint = SPARQLWrapper(endpoint_url)
#     # sparql_endpoint.setQuery(GET_VOID_DESC)
#     # sparql_endpoint.setReturnFormat("json")

#     void_dict = {}
#     try:
#         # void_res = sparql_endpoint.query().convert()
#         # NOTE: Build a dict[subject_cls][predicate] = list[object_cls/datatype]
#         print("GONNA QUERY!")
#         for row in g.query(GET_VOID_DESC):
#             # print("DONE QUERY")
#             # print(row)
#             if str(row.class1) not in void_dict:
#                 void_dict[str(row.class1)] = {}
#             if str(row.prop) not in void_dict[str(row.class1)]:
#                 void_dict[str(row.class1)][str(row.prop)] = []
#             if "class2" in row:
#                 print(row.class2)
#                 void_dict[str(row.class1)][str(row.prop)].append(
#                     str(row.class2)
#                 )
#             if "datatype" in row:
#                 print(row.datatype)
#                 void_dict[str(row.class1)][str(row.prop)].append(
#                     str(row.datatype)
#                 )
#         if len(void_dict) == 0:
#             raise Exception("No VoID description found in the endpoint")
#     except Exception as e:
#         print(f"Could not retrieve VoID description: {e}")
#     return void_dict