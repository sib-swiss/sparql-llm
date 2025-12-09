import warnings
from typing import Any

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from rdflib.plugins.sparql import prepareQuery

from sparql_llm.utils import get_prefixes_for_endpoint, logger, query_sparql

GET_SPARQL_EXAMPLES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX spex: <https://purl.expasy.org/sparql-examples/ontology#>
SELECT DISTINCT ?sq ?comment ?query
WHERE {
    ?sq a sh:SPARQLExecutable ;
        rdfs:comment ?comment ;
        sh:select|sh:ask|sh:construct|spex:describe ?query .
} ORDER BY ?sq"""


class SparqlExamplesLoader(BaseLoader):
    """
    Load SPARQL queries examples from a SPARQL endpoint stored using the SHACL ontology as documents.
    Compatible with the LangChain framework.
    """

    def __init__(self, endpoint_url: str, examples_file: str | None = None):
        """
        Initialize the SparqlExamplesLoader.

        Args:
            endpoint_url (str): URL of the SPARQL endpoint to retrieve SPARQL queries examples from.
        """
        self.endpoint_url = endpoint_url
        self.examples_file = examples_file

    def load(self) -> list[Document]:
        """Load and return documents from the SPARQL endpoint."""
        docs: list[Document] = []
        prefix_map: dict[str, str] = {}
        try:
            prefix_map = get_prefixes_for_endpoint(self.endpoint_url, self.examples_file)
            for row in query_sparql(
                GET_SPARQL_EXAMPLES_QUERY, self.endpoint_url, use_file=self.examples_file, check_service_desc=True
            )["results"]["bindings"]:
                docs.append(self._create_document(row, prefix_map))
        except Exception as e:
            logger.warning(f"Could not retrieve SPARQL query examples from endpoint {self.endpoint_url}: {e}")

        logger.info(f"Found {len(docs)} examples queries for {self.endpoint_url}")
        return docs

    def _create_document(self, row: Any, prefix_map: dict[str, str]) -> Document:
        """Create a Document object from a query result row."""
        comment = self._remove_a_tags(row["comment"]["value"])
        query = row["query"]["value"]
        # Add prefixes to query if not already present
        # NOTE: legacy, was adding prefixes that were missing
        # for prefix, namespace in prefix_map.items():
        #     prefix_str = f"PREFIX {prefix}: <{namespace}>"
        #     if not re.search(prefix_str, query) and re.search(f"[(| |\u00a0|/]{prefix}:", query):
        #         query = f"{prefix_str}\n{query}"
        query_type = None
        try:
            query_type = prepareQuery(query).algebra.name
        except Exception as e:
            logger.warning(f"Could not parse query: {query}. Error: {e}")
        return Document(
            page_content=comment,
            metadata={
                "question": comment,
                "answer": query,
                "endpoint_url": self.endpoint_url,
                "query_type": query_type,
                "doc_type": "SPARQL endpoints query examples",
            },
        )

    def _remove_a_tags(self, html_text: str) -> str:
        """Remove all <a> tags from the queries descriptions"""
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        soup = BeautifulSoup(html_text, "html.parser")
        for a_tag in soup.find_all("a"):
            a_tag.replace_with(a_tag.text)
        return str(soup.get_text())
