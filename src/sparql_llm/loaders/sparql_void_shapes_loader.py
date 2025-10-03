from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from sparql_llm.utils import (
    get_prefix_converter,
    get_prefixes_for_endpoint,
    get_schema_for_endpoint,
    logger,
    query_sparql,
)

DEFAULT_NAMESPACES_TO_IGNORE = [
    "http://www.w3.org/ns/sparql-service-description#",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/2002/07/owl#",
    "http://rdfs.org/ns/void#",
    "http://purl.org/query/voidext#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/2000/01/rdf-schema#",
]


def ignore_namespaces(ns_to_ignore: list[str], cls: str) -> bool:
    return any(cls.startswith(ns) for ns in ns_to_ignore)


def get_shex_dict_from_void(
    endpoint_url: str,
    prefix_map: dict[str, str] | None = None,
    namespaces_to_ignore: list[str] | None = None,
    void_file: str | None = None,
    examples_file: str | None = None,
) -> dict[str, dict[str, str]]:
    """Get a dict of shex shapes from the VoID description."""
    prefix_map = prefix_map or get_prefixes_for_endpoint(endpoint_url, examples_file)
    namespaces_to_ignore = namespaces_to_ignore or DEFAULT_NAMESPACES_TO_IGNORE
    prefix_converter = get_prefix_converter(prefix_map)
    void_dict = get_schema_for_endpoint(endpoint_url, void_file)
    shex_dict = {}

    for subject_cls, predicates in void_dict.items():
        if ignore_namespaces(namespaces_to_ignore, subject_cls):
            continue
        try:
            subj = prefix_converter.compress(subject_cls, passthrough=True)
        except Exception as _e:
            subj = f"<{subject_cls}>"
        shape_iri = f"shape:{subj.replace(':', '_')}"
        shex_dict[subject_cls] = {"shex": f"{shape_iri} {{\n  a [ {subj} ] ;\n"}

        for predicate, object_list in predicates.items():
            try:
                pred = prefix_converter.compress(predicate, passthrough=True)
            except Exception as _e:
                pred = f"<{predicate}>"

            # compressed_obj_list = compress_list(prefix_converter, object_list)
            compressed_obj_list = []
            for obj in object_list:
                try:
                    compressed_obj_list.append(prefix_converter.compress(obj, passthrough=True))
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
    void_dict = {}
    try:
        label_res = query_sparql(get_labels_query, endpoint_url, post=True, check_service_desc=True)
        for label_triple in label_res["results"]["bindings"]:
            cls = label_triple["cls"]["value"]
            if cls not in shex_dict:
                continue
            shex_dict[cls]["label"] = label_triple["label"]["value"]
            if "comment" in label_triple:
                # shex_dict[cls]["label"] += f": {label_triple['comment']['value']}"
                shex_dict[cls]["comment"] = label_triple["comment"]["value"]
    except Exception as e:
        logger.warning(f"Could not retrieve labels for classes in endpoint {endpoint_url}: {e}")

    return shex_dict


def get_shex_from_void(
    endpoint_url: str,
    namespaces_to_ignore: list[str] | None = None,
    void_file: str | None = None,
    examples_file: str | None = None,
) -> str:
    """Function to build complete ShEx from VoID description with prefixes and all shapes"""
    prefix_map = get_prefixes_for_endpoint(endpoint_url, examples_file)
    shex_dict = get_shex_dict_from_void(endpoint_url, prefix_map, namespaces_to_ignore, void_file, examples_file)
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


class SparqlVoidShapesLoader(BaseLoader):
    """
    Load ShEx shapes built from the pre-compiled VoID description of classes present in a SPARQL endpoint as documents.
    Compatible with the LangChain framework.
    """

    def __init__(
        self,
        endpoint_url: str,
        void_file: str | None = None,
        examples_file: str | None = None,
        namespaces_to_ignore: list[str] | None = None,
        prefix_map: dict[str, str] | None = None,
    ):
        """
        Initialize the SparqlVoidShapesLoader.

        Args:
            endpoint_url (str): URL of the SPARQL endpoint to retrieve SPARQL queries examples from.
        """
        self.endpoint_url = endpoint_url
        self.void_file = void_file
        self.examples_file = examples_file
        self.prefix_map = prefix_map
        self.namespaces_to_ignore = namespaces_to_ignore

    def load(self) -> list[Document]:
        """Load and return documents from the SPARQL endpoint."""
        docs: list[Document] = []
        shex_dict = get_shex_dict_from_void(
            self.endpoint_url, self.prefix_map, self.namespaces_to_ignore, self.void_file, self.examples_file
        )

        for cls_uri, shex_shape in shex_dict.items():
            # print(cls_uri, shex_shape)
            metadata_dict = {
                "answer": shex_shape["shex"],
                "endpoint_url": self.endpoint_url,
                "iri": cls_uri,
                "doc_type": "SPARQL endpoints classes schema",
            }
            if "label" in shex_shape:
                docs.append(
                    Document(
                        page_content=shex_shape["label"],
                        metadata={"question": shex_shape["label"], **metadata_dict},
                    )
                )
            else:
                docs.append(
                    Document(
                        page_content=cls_uri,
                        metadata={"question": cls_uri, **metadata_dict},
                    )
                )
            # We add a separate document for the comment if it exists
            if "comment" in shex_shape:
                docs.append(
                    Document(
                        page_content=shex_shape["comment"],
                        metadata={"question": shex_shape["comment"], **metadata_dict},
                    )
                )

        logger.info(f"Extracted {len(docs)} ShEx shapes for {self.endpoint_url}")
        return docs
