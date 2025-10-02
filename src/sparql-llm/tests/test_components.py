import os

from sparql_llm import (
    SparqlExamplesLoader,
    SparqlVoidShapesLoader,
    validate_sparql_with_void,
)
from sparql_llm.utils import get_schema_for_endpoint


def test_sparql_examples_loader_uniprot():
    """Test the SPARQL queries examples loader with the UniProt endpoint."""
    loader = SparqlExamplesLoader("https://sparql.uniprot.org/sparql/")
    docs = loader.load()
    # print(docs)
    assert len(docs) >= 10


def test_sparql_void_shape_loader_uniprot():
    loader = SparqlVoidShapesLoader("https://sparql.uniprot.org/sparql/")
    docs = loader.load()
    # print(docs)
    assert len(docs) >= 10


def test_sparql_void_shape_loader_bgee():
    loader = SparqlVoidShapesLoader("https://www.bgee.org/sparql/")
    docs = loader.load()
    assert len(docs) >= 10


# uv run pytest tests/test_components.py::test_sparql_void_from_url
def test_sparql_void_from_file():
    void_filepath = os.path.join(os.path.dirname(__file__), "void_uniprot.ttl")
    void_dict = get_schema_for_endpoint("https://sparql.uniprot.org/", void_filepath)
    # From URL: void_dict = get_void_for_endpoint("https://sparql.uniprot.org/", "https://sparql.uniprot.org/.well-known/void/")
    assert len(void_dict) >= 2


def test_validate_sparql_with_void():
    sparql_query = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX genex: <http://purl.org/genex#>
PREFIX sio: <http://semanticscience.org/resource/>
SELECT DISTINCT ?humanProtein ?orthologRatProtein ?orthologRatGene
WHERE {
    ?humanProtein a orth:Protein ;
        lscr:xrefUniprot <http://purl.uniprot.org/uniprot/Q9Y2T1> .
    ?orthologRatProtein a orth:Protein ;
        sio:SIO_010078 ?orthologRatGene ;
        orth:organism/obo:RO_0002162/up:commonName 'Rattus norvegicus' .
    ?cluster a orth:OrthologsCluster .
    ?cluster orth:hasHomologousMember ?node1 .
    ?cluster orth:hasHomologousMember ?node2 .
    ?node1 orth:hasHomologousMember* ?humanProtein .
    ?node2 orth:hasHomologousMember* ?orthologRatProtein .
    FILTER(?node1 != ?node2)
    SERVICE <https://www.bgee.org/sparql/> {
        ?orthologRatGene a orth:Gene ;
            genex:expressedIn ?anatEntity ;
            orth:organism ?ratOrganism .
        ?anatEntity rdfs:label 'brain' .
        ?ratOrganism obo:RO_0002162 taxon:10116 .
    }
}"""
    issues = validate_sparql_with_void(sparql_query, "https://sparql.omabrowser.org/sparql/")
    print("\n".join(issues))
    assert len(issues) == 3


# def test_sparql_examples_loader_error_nextprot():
#     """Test the SPARQL queries examples loader with the UniProt endpoint."""
#     try:
#         loader = SparqlExamplesLoader("https://sparql.nextprot.orgg/")
#         _docs = loader.load()
#         raise AssertionError("Should have raised an error")
#     except Exception as e:
#         assert "Failed to resolve" in str(e)
