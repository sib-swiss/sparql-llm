from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from sparql_llm.utils import SparqlEndpointLinks, logger

GENERAL_INFO_DOC_TYPE = "General information"


class SparqlInfoLoader(BaseLoader):
    """Load informations for a list of SPARQL endpoints."""

    def __init__(
        self,
        endpoints: list[SparqlEndpointLinks],
        source_iri: str | None = None,
        org_label: str = "",
        service_label: str = "",
    ):
        """Initialize the SparqlInfoLoader."""
        self.endpoints = endpoints
        self.source_iri = source_iri
        self.org_label = org_label
        self.service_label = service_label

    def load(self) -> list[Document]:
        """Load and return documents from the SPARQL endpoint."""
        docs: list[Document] = []

        resources_summary_question = (
            f"Which resources are supported by {self.service_label}?"
            if self.service_label
            else "Which resources are supported by this system?"
        )
        metadata = {
            "question": resources_summary_question,
            "answer": f"This system helps to access the following SPARQL endpoints {self.org_label}:\n- "
            + "\n- ".join(
                [
                    f"{endpoint.get('label')} ({endpoint['endpoint_url']}): {endpoint.get('description')}"
                    if endpoint.get("label") and endpoint.get("description")
                    else f"{endpoint.get('label')} ({endpoint['endpoint_url']})"
                    if endpoint.get("label")
                    else f"{endpoint['endpoint_url']}: {endpoint.get('description')}"
                    if endpoint.get("description")
                    else f"{endpoint['endpoint_url']}"
                    for endpoint in self.endpoints
                ]
            ),
            "doc_type": GENERAL_INFO_DOC_TYPE,
        }
        if self.source_iri:
            metadata["iri"] = self.source_iri
        docs.append(
            Document(
                page_content=resources_summary_question,
                metadata=metadata,
            )
        )

        logger.info(f"Added {len(docs)} documents with general informations")
        return docs
