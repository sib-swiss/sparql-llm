from typing import Optional

from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from sparql_llm.void_to_shex import get_shex_dict_from_void


class SparqlVoidShapesLoader(BaseLoader):
    """
    Load ShEx shapes built from the pre-compiled VoID description of classes present in a SPARQL endpoint as documents.
    Compatible with the LangChain framework.
    """

    def __init__(
        self,
        endpoint_url: str,
        namespaces_to_ignore: Optional[list[str]] = None,
        prefix_map: Optional[dict[str, str]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the SparqlVoidShapesLoader.

        Args:
            endpoint_url (str): URL of the SPARQL endpoint to retrieve SPARQL queries examples from.
        """
        self.endpoint_url = endpoint_url
        self.prefix_map = prefix_map
        self.namespaces_to_ignore = namespaces_to_ignore
        self.verbose = verbose

    def load(self) -> list[Document]:
        """Load and return documents from the SPARQL endpoint."""
        docs: list[Document] = []
        shex_dict = get_shex_dict_from_void(self.endpoint_url, self.prefix_map, self.namespaces_to_ignore)

        for cls_uri, shex_shape in shex_dict.items():
            # print(cls_uri, shex_shape)
            metadata_dict = {
                "answer": shex_shape["shex"],
                "endpoint_url": self.endpoint_url,
                "class_uri": cls_uri,
                "doc_type": "shex",
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

        if self.verbose:
            print(f"Extracted {len(docs)} ShEx shapes for {self.endpoint_url}")
        return docs
