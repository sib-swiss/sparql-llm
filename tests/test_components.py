from sparql_llm import (
    SparqlExamplesLoader,
    SparqlVoidShapesLoader,
    __version__,
    validate_sparql_with_void,
)


def test_sparql_examples_loader_uniprot():
    """Test the SPARQL queries examples loader with the UniProt endpoint."""
    loader = SparqlExamplesLoader("https://sparql.uniprot.org/sparql/")
    docs = loader.load()
    # print(docs)
    assert len(docs) >= 10


# def test_sparql_examples_loader_error_nextprot():
#     """Test the SPARQL queries examples loader with the UniProt endpoint."""
#     try:
#         loader = SparqlExamplesLoader("https://sparql.nextprot.orgg/")
#         _docs = loader.load()
#         raise AssertionError("Should have raised an error")
#     except Exception as e:
#         assert "Failed to resolve" in str(e)


def test_sparql_void_shape_loader():
    loader = SparqlVoidShapesLoader("https://sparql.uniprot.org/sparql/")
    docs = loader.load()
    # print(docs)
    assert len(docs) >= 10


def test_validate_sparql_with_void():
    sparql_query = """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX up:<http://purl.uniprot.org/core/>
PREFIX taxon:<http://purl.uniprot.org/taxonomy/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth:<http://purl.org/net/orth#>
PREFIX dcterms:<http://purl.org/dc/terms/>
PREFIX obo:<http://purl.obolibrary.org/obo/>
PREFIX lscr:<http://purl.org/lscr#>
PREFIX genex:<http://purl.org/genex#>
PREFIX sio: <http://semanticscience.org/resource/>
SELECT DISTINCT ?diseaseLabel ?humanProtein ?hgncSymbol ?orthologRatProtein ?orthologRatGene
WHERE {
    SERVICE <https://sparql.uniprot.org/sparql> {
        SELECT DISTINCT * WHERE {
            ?humanProtein a up:Protein ;
                up:organism/up:scientificName 'Homo sapiens' ;
                up:annotation ?annotation ;
                rdfs:seeAlso ?hgnc .
            ?hgnc up:database <http://purl.uniprot.org/database/HGNC> ;
                rdfs:label ?hgncSymbol . # comment
            ?annotation a up:Disease_Annotation ;
                up:disease ?disease .
            ?disease a up:Disease ;
                rdfs:label ?diseaseLabel . # skos:prefLabel
            FILTER CONTAINS(?diseaseLabel, "cancer")
        }
    }
    SERVICE <https://sparql.omabrowser.org/sparql/> {
        SELECT ?humanProtein ?orthologRatProtein ?orthologRatGene WHERE {
            ?humanProteinOma a orth:Protein ;
                lscr:xrefUniprot ?humanProtein .
            ?orthologRatProtein a orth:Protein ;
                sio:SIO_010078 ?orthologRatGene ; # 79
                orth:organism/obo:RO_0002162/up:scientificNam 'Rattus norvegicus' .
            ?cluster a orth:OrthologsCluster .
            ?cluster orth:hasHomologousMember ?node1 .
            ?cluster orth:hasHomologousMember ?node2 .
            ?node1 orth:hasHomologousMember* ?humanProteinOma .
            ?node2 orth:hasHomologousMember* ?orthologRatProtein .
            FILTER(?node1 != ?node2)
        }
    }
    SERVICE <https://www.bgee.org/sparql/> {
        ?orthologRatGene genex:isExpressedIn ?anatEntity ;
            orth:organism ?ratOrganism .
        ?anatEntity rdfs:label 'brain' .
        ?ratOrganism obo:RO_0002162 taxon:10116 .
    }
}"""
    issues = validate_sparql_with_void(sparql_query, "https://sparql.uniprot.org/sparql/")
    # print("\n".join(issues))
    assert len(issues) == 4


def test_version():
    """Test the version is a string."""
    assert isinstance(__version__, str)
