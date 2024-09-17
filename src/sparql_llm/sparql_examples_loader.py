import re
import warnings
from typing import Any

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from rdflib.plugins.sparql import prepareQuery

from sparql_llm.utils import GET_PREFIXES_QUERY, query_sparql

GET_SPARQL_EXAMPLES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?comment ?query
WHERE {
    ?sq a sh:SPARQLExecutable ;
        rdfs:comment ?comment ;
        sh:select|sh:ask|sh:construct|sh:describe ?query .
} ORDER BY ?sq"""


class SparqlExamplesLoader(BaseLoader):
    """
    Load SPARQL queries examples from a SPARQL endpoint stored using the SHACL ontology as documents.
    Compatible with the LangChain framework.
    """

    def __init__(self, endpoint_url: str, verbose: bool = False):
        """
        Initialize the SparqlExamplesLoader.

        Args:
            endpoint_url (str): URL of the SPARQL endpoint to retrieve SPARQL queries examples from.
        """
        self.endpoint_url = endpoint_url
        self.verbose = verbose

    def load(self) -> list[Document]:
        """Load and return documents from the SPARQL endpoint."""
        docs: list[Document] = []

        # Get prefixes
        prefix_map: dict[str, str] = {}
        try:
            res = query_sparql(GET_PREFIXES_QUERY, self.endpoint_url)
            for row in res["results"]["bindings"]:
                # TODO: we might be able to remove this soon, when prefixes will be included in all endpoints
                prefix_map[row["prefix"]["value"]] = row["namespace"]["value"]

            for row in query_sparql(GET_SPARQL_EXAMPLES_QUERY, self.endpoint_url)["results"]["bindings"]:
                docs.append(self._create_document(row, prefix_map))
        except Exception as e:
            print(f"Could not retrieve SPARQL query examples from endpoint {self.endpoint_url}: {e}")

        if self.verbose:
            print(f"Found {len(docs)} examples queries for {self.endpoint_url}")
        return docs

    def _create_document(self, row: Any, prefix_map: dict[str, str]) -> Document:
        """Create a Document object from a query result row."""
        comment = self._remove_a_tags(row["comment"]["value"])
        query = row["query"]["value"]
        # Add prefixes to query if not already present
        # TODO: we might be able to remove this now that prefixes are included
        for prefix, namespace in prefix_map.items():
            prefix_str = f"PREFIX {prefix}: <{namespace}>"
            if not re.search(prefix_str, query) and re.search(f"[(| |\u00a0|/]{prefix}:", query):
                query = f"{prefix_str}\n{query}"

        parsed_query = prepareQuery(query)
        return Document(
            page_content=comment,
            metadata={
                "question": comment,
                "answer": query,
                "endpoint_url": self.endpoint_url,
                "query_type": parsed_query.algebra.name,
                "doc_type": "sparql_query",
            },
        )

    def _remove_a_tags(self, html_text: str) -> str:
        """Remove all <a> tags from the queries descriptions"""
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        soup = BeautifulSoup(html_text, "html.parser")
        for a_tag in soup.find_all("a"):
            a_tag.replace_with(a_tag.text)
        return str(soup.get_text())
