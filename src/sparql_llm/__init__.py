"""Utilities to improve LLMs capabilities when working with SPARQL and RDF."""

__version__ = "0.0.2"

from .void_to_shex import get_shex_dict_from_void
from .validate_sparql import validate_sparql_with_void
from .sparql_examples_loader import SparqlExamplesLoader
from .sparql_void_shapes_loader import SparqlVoidShapesLoader
