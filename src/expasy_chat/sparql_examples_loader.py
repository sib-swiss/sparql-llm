import re
from typing import Any

from SPARQLWrapper import SPARQLWrapper
from bs4 import BeautifulSoup
from langchain_core.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.stores.sparqlstore import SPARQLStore

from expasy_chat.utils import GET_PREFIXES_QUERY

GET_SPARQL_EXAMPLES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?comment ?query
WHERE {
    ?sq a sh:SPARQLExecutable ;
        rdfs:label|rdfs:comment ?comment ;
        sh:select|sh:ask|sh:construct|sh:describe ?query .
} ORDER BY ?sq"""


class SparqlExamplesLoader(BaseLoader):
    """
    Load SPARQL queries examples from a SPARQL endpoint stored using the SHACL ontology as documents.
    Compatible with the LangChain framework.
    """

    def __init__(self, endpoint_url: str, endpoint_auth: tuple[str, str] | None = None, verbose: bool = False):
        """
        Initialize the SparqlExamplesLoader.

        Args:
            endpoint_url (str): URL of the SPARQL endpoint to retrieve SPARQL queries examples from.
        """
        self.endpoint_url = endpoint_url
        self.verbose = verbose
        # self.graph = Graph(SPARQLStore(endpoint_url, auth=endpoint_auth), bind_namespaces="none")
        self.sparql_endpoint = SPARQLWrapper(endpoint_url)
        # self.sparql_endpoint.setMethod("POST")
        self.sparql_endpoint.setReturnFormat("json")
        # try:
        #     self.graph.query("ASK { ?s ?p ?o }")
        # except ValueError as e:
        #     raise ValueError(f"Could not query the provided endpoint at {endpoint_url}: {e}") from e

    def load(self) -> list[Document]:
        """Load and return documents from the SPARQL endpoint."""
        docs: list[Document] = []

        # Get prefixes
        prefix_map: dict[str, str] = {}
        print("GETTING PREFIXES")
        try:
            self.sparql_endpoint.setQuery(GET_PREFIXES_QUERY)
            res = self.sparql_endpoint.query().convert()
            for row in res["results"]["bindings"]:
                # TODO: we might be able to remove this now that prefixes are included
                prefix_map[row["prefix"]["value"]] = row["namespace"]["value"]

            self.sparql_endpoint.setQuery(GET_SPARQL_EXAMPLES_QUERY)
            for row in self.sparql_endpoint.query().convert()["results"]["bindings"]:
                docs.append(self._create_document(row, prefix_map))
        except Exception as e:
            print(f"Could not retrieve SPARQL examples from endpoint {self.endpoint_url}: {e}")

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
        soup = BeautifulSoup(html_text, "html.parser")
        for a_tag in soup.find_all("a"):
            a_tag.replace_with(a_tag.text)
        return soup.get_text()
