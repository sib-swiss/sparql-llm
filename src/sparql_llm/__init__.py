"""Utilities to improve LLMs capabilities when working with SPARQL and RDF."""

__version__ = "0.1.3"

from .utils import SparqlEndpointLinks, query_sparql
from .validate_sparql import validate_sparql, validate_sparql_in_msg, validate_sparql_with_void
from .loaders.sparql_examples_loader import SparqlExamplesLoader
from .loaders.sparql_void_shapes_loader import SparqlVoidShapesLoader, get_shex_dict_from_void, get_shex_from_void
from .loaders.sparql_info_loader import SparqlInfoLoader
