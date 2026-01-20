import logging
import os
import sys
import time
from collections import defaultdict

import httpx
import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from sparql_llm.agent.prompts import RESOLUTION_PROMPT
from sparql_llm.agent.utils import load_chat_model
from sparql_llm.config import Configuration, settings
from sparql_llm.utils import query_sparql
from sparql_llm.validate_sparql import extract_sparql_queries

file_time_prefix = time.strftime("%Y%m%d_%H%M")
bench_folder = os.path.join("data", "benchmarks")
os.makedirs(bench_folder, exist_ok=True)

# Setup logging to both console and file
logger = logging.getLogger("benchmark")
# Disable the default console handler
logger.propagate = False
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(os.path.join(bench_folder, f"{file_time_prefix}_tests_output.md"), mode="w")
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

# Suppress overly verbose logs from httpx
# logging.getLogger("httpx").setLevel(logging.WARNING)


# TODO: which genes expressed in mice correspond to human proteins linked to diabetes?
# how can i analyse protein-protein interactions
# Which resources can I use to model protein folding?

example_queries = [
    {
        "question": "What is the accession number in uniprot of the human gene LCT? Return only unique protein URIs",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
SELECT DISTINCT ?protein
WHERE{
    ?protein a up:Protein .
    ?protein up:organism taxon:9606 .
    ?protein up:encodedBy ?gene .
    ?gene skos:prefLabel "LCT" .
}""",
    },
    {
        # NOTE: The "mature" part in the question makes it harder to answer
        # "question": "How do I filter for reviewed (mouse) proteins whose mature form carries an N-terminal glycine? Return protein URI and AA sequence",
        "question": "How do I filter for reviewed mouse proteins which carry an N-terminal glycine? Return ?protein URI and AA ?sequence",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?protein ?sequence
WHERE
{
    ?protein a up:Protein ;
        up:organism taxon:10090 ;  # Taxonomy ID for Mus musculus (Mouse)
        up:reviewed true ;
        up:sequence ?isoform .
    ?isoform rdf:value ?sequence .
    # Ensure the N-terminal amino acid is Glycine (G)
    FILTER (STRSTARTS(?sequence, "G"))
}""",
    },
    {
        "question": "How could I download a table that only includes the Rhea reactions for which there is experimental evidence? Return only the ?rhea URI",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?rhea
WHERE {
# ECO 269 is experimental evidence
BIND (<http://purl.obolibrary.org/obo/ECO_0000269> as ?evidence)
#GRAPH <http://sparql.uniprot.org/uniprot> {
    ?protein up:reviewed true ;
    up:annotation ?a ;
    up:attribution ?attribution  .

    ?a a up:Catalytic_Activity_Annotation ;
    up:catalyticActivity ?ca .
    ?ca up:catalyzedReaction ?rhea .

    [] rdf:subject ?a ;
    rdf:predicate up:catalyticActivity ;
    rdf:object ?ca ;
    up:attribution ?attribution .

    ?attribution up:evidence ?evidence .
#}
}""",
    },
    {
        "question": "Which human proteins are enzymes catalyzing a reaction involving sterols? Return the protein, sterol and reaction URI",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX rh: <http://rdf.rhea-db.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX CHEBI: <http://purl.obolibrary.org/obo/CHEBI_>
SELECT DISTINCT ?protein ?sterol ?reaction
WHERE {
SERVICE <https://sparql.rhea-db.org/sparql> {
    ?reaction rdfs:subClassOf rh:Reaction .
    ?reaction rh:side/rh:contains/rh:compound ?compound .
    ?compound rh:chebi ?sterol .
    ?sterol rdfs:subClassOf* CHEBI:15889 .
}
?protein a up:Protein ;
    up:organism taxon:9606 ;
    up:annotation/up:catalyticActivity/up:catalyzedReaction ?reaction .
}""",
    },
    {
        # "question": "Which are the human proteins associated with cancer (which have cancer in their disease label)? Return the unique disease label (?diseaseLabel), and HGNC symbol (?hgncSymbol)",
        "question": "Which are the human proteins associated with cancer? Return distinct ?diseaseLabel and ?hgncSymbol",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX up:<http://purl.uniprot.org/core/>
PREFIX taxon:<http://purl.uniprot.org/taxonomy/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth:<http://purl.org/net/orth#>
PREFIX dcterms:<http://purl.org/dc/terms/>
PREFIX obo:<http://purl.obolibrary.org/obo/>
PREFIX lscr:<http://purl.org/lscr#>
PREFIX genex:<http://purl.org/genex#>
PREFIX sio: <http://semanticscience.org/resource/>
SELECT DISTINCT ?diseaseLabel ?hgncSymbol
WHERE {
    ?humanProtein a up:Protein ;
        # up:organism/up:scientificName 'Homo sapiens' ;
        up:organism taxon:9606 ;
        up:annotation ?annotation ;
        rdfs:seeAlso ?hgnc .
    ?hgnc up:database <http://purl.uniprot.org/database/HGNC> ;
        rdfs:comment ?hgncSymbol .
    ?annotation a up:Disease_Annotation ;
        up:disease ?disease .
    ?disease skos:prefLabel ?diseaseLabel.
    FILTER CONTAINS (LCASE(?diseaseLabel), "cancer")
}""",
    },
    {
        "question": "In bgee how can I retrieve the confidence level and false discovery rate of a gene expression? Return distinct ?gene, ?confidence and ?fdr, limit to 10",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX genex: <http://purl.org/genex#>
PREFIX bgee: <http://bgee.org/#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
SELECT DISTINCT ?gene ?confidence ?fdr
WHERE {
    ?expression a genex:Expression ;
        genex:hasConfidenceLevel ?confidence ;
        genex:hasFDRpvalue ?fdr ;
        genex:hasSequenceUnit ?gene .
} LIMIT 10""",
    },
    {
        # There are no example with xrefEnsembl, so the RAG without validation usually fails
        "question": "How can I get the cross-reference to the ensembl protein for the LCT protein in OMA? Return only the distinct ?ensemblURI",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX orth: <http://purl.org/net/orth#>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?ensemblURI
WHERE {
    ?protein a orth:Protein ;
        rdfs:label 'LCT' ;
        lscr:xrefEnsemblProtein ?ensemblURI .
}""",
    },
    {
        # There are no example with inDataset
        "question": "How can I get the URI of a dataset to which an ortholog cluster belongs in OMA? Return orthologCluster, datasetURI and limit to 20",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX orth: <http://purl.org/net/orth#>
SELECT DISTINCT ?orthologCluster ?datasetURI
WHERE {
    ?orthologCluster a orth:OrthologsCluster ;
        orth:inDataset ?datasetURI .
} LIMIT 20""",
    },
    {
        "question": "Give me the list of strains associated to the Escherichia coli taxon and their name. Return ?taxon, ?strain, ?name, limit to 20",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?taxon ?strain ?name
WHERE {
    ?taxon a up:Taxon .
    ?taxon rdfs:subClassOf taxon:562 . # Escherichia coli taxon
    ?taxon up:strain ?strain .
    ?strain up:name ?name .
} LIMIT 20""",
    },
    {
        "question": "Retrieve all proteins involved in pathways involving glycolysis. Return ?proteinURI, ?proteinLabel, ?pathwayLabel, limit to 20",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?proteinURI ?proteinLabel ?pathwayLabel
WHERE {
    ?proteinURI a up:Protein ;
        up:recommendedName/up:fullName ?proteinLabel ;
        up:annotation ?annotation .
    ?annotation a up:Pathway_Annotation ;
        rdfs:seeAlso ?pathway .
    ?pathway rdfs:label ?pathwayLabel .
    FILTER(CONTAINS(LCASE(?pathwayLabel), "glycolysis"))
} LIMIT 20""",
    },
    {
        "question": "What are the orthologs in rat for protein Q9Y2T1? Return ?ratProtein ?ratUniProtXref",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
SELECT DISTINCT ?ratProtein ?ratUniProtXref
WHERE {
    ?cluster a orth:OrthologsCluster.
    ?cluster orth:hasHomologousMember ?node1.
    ?cluster orth:hasHomologousMember ?node2.
    ?node1 orth:hasHomologousMember* ?humanProtein.
    ?node2 orth:hasHomologousMember* ?ratProtein.
    ?humanProtein a orth:Protein;
        lscr:xrefUniprot <http://purl.uniprot.org/uniprot/Q9Y2T1>.
    ?ratProtein a orth:Protein;
        orth:organism/obo:RO_0002162/up:scientificName 'Rattus norvegicus';
        lscr:xrefUniprot ?ratUniProtXref.
    FILTER(?node1 != ?node2)
}""",
    },
    # 2 of the queries used as examples in the web UI:
    {
        "question": "What are the rat orthologs of the human TP53? Return ?ratProteinUri ?ratUniprotLink",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX sio: <http://semanticscience.org/resource/>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX obo: <http://purl.obolibrary.org/obo/>

SELECT DISTINCT ?ratProteinUri ?ratUniprotLink WHERE {
    ?humanProtein a orth:Protein ;
        rdfs:label 'TP53' ;
        orth:organism/obo:RO_0002162/up:scientificName 'Homo sapiens' .
    ?cluster a orth:OrthologsCluster ;
        orth:hasHomologousMember ?node1 ;
        orth:hasHomologousMember ?node2 .
    ?node1 orth:hasHomologousMember* ?humanProtein .
    ?node2 orth:hasHomologousMember* ?ratProteinUri .
    ?ratProteinUri a orth:Protein ;
        orth:organism/obo:RO_0002162/up:scientificName 'Rattus norvegicus' ;
        lscr:xrefUniprot ?ratUniprotLink .
    FILTER(?node1 != ?node2)
}""",
    },
    {
        "question": "Where is expressed the gene ACE2 in human? Return ?anatUri ?anatName",
        "endpoint": "https://www.bgee.org/sparql/",
        "query": """PREFIX genex: <http://purl.org/genex#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX up: <http://purl.uniprot.org/core/>

SELECT DISTINCT ?anatUri ?anatName WHERE {
    ?seq a orth:Gene ;
        genex:isExpressedIn ?anatUri ;
        rdfs:label "ACE2" ;
        orth:organism ?organism .
    ?anatUri a genex:AnatomicalEntity ;
        rdfs:label ?anatName .
    ?organism obo:RO_0002162 ?species .
    ?species a up:Taxon ;
        up:scientificName "Homo sapiens" .
}""",
    },
    {
        "question": """Retrieve all proteins that are associated with Alzheimer disease (http://purl.uniprot.org/diseases/3832) and where they are known to be located in the cell. Return ?proteinURI, ?locationInsideCellLabel, ?locationInsideCellUri, limit to 20""",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?proteinURI ?locationInsideCellLabel ?locationInsideCellUri
WHERE {
    ?proteinURI a up:Protein ;
        up:annotation ?diseaseAnnotation , ?subcellAnnotation .
    ?diseaseAnnotation up:disease <http://purl.uniprot.org/diseases/3832> .
    ?subcellAnnotation up:locatedIn/up:cellularComponent ?locationInsideCellUri .
    ?locationInsideCellUri skos:prefLabel ?locationInsideCellLabel .
} LIMIT 20""",
    },
    {
        "question": "Retrieve all proteins in OMA that are encoded by the TP53 gene and their mnemonics and evidence types from the UniProt database. Return ?proteinOMA ?speciesLabel ?mnemonic ?evidenceType ?uniprotURI",
        "endpoint": "https://sparql.omabrowser.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX lscr: <http://purl.org/lscr#>
SELECT DISTINCT ?proteinOMA ?speciesLabel ?mnemonic ?evidenceType ?uniprotURI
WHERE {
    ?proteinOMA a orth:Protein ;
        orth:organism/obo:RO_0002162/up:scientificName ?speciesLabel ;
        rdfs:label 'TP53' .
    ?proteinOMA lscr:xrefUniprot ?uniprotURI.
    SERVICE <http://sparql.uniprot.org/sparql> {
        ?uniprotURI up:mnemonic ?mnemonic ;
            up:existence/rdfs:label ?evidenceType .
    }
}
""",
    },
    {
        "question": "What is the function of APOC1? Return ?function",
        "endpoint": "https://sparql.uniprot.org/sparql/",
        "query": """PREFIX up: <http://purl.uniprot.org/core/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT DISTINCT ?function WHERE {
    ?protein a up:Protein ;
        up:mnemonic "APOC1_HUMAN" ;
        up:annotation ?annotation .
    ?annotation a up:Function_Annotation ;
        rdfs:comment ?function .
}
""",
    },
    #################################################################
    # New queries to test:
    # What are the genes expressed in the human brain?
    # FAILS to add filter for human
    # What are the human genes expressed in the brain? WORKS as expected
    # Which are the human genes associated with cancer and their orthologs?
    # This one does not work because in the query generated the variable in the UniProt block ?protein does not match the one used in the OMA block, ?humanUniprot...
    # TODO: when we parse the query check there is a link between the two blocks (2 block are using the same variable)
    # https://sibkru.atlassian.net/jira/software/projects/E4/boards/6?selectedIssue=E4-34
    #     {
    #         "question": "Which are the human genes associated with cancer and their orthologs? Return ?humanGeneName ?orthologUniprot, and limit to 10",
    #         "endpoint": "https://sparql.uniprot.org/sparql/",
    #         "query": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    # PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    # PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
    # PREFIX up: <http://purl.uniprot.org/core/>
    # PREFIX orth: <http://purl.org/net/orth#>
    # PREFIX lscr: <http://purl.org/lscr#>
    # SELECT DISTINCT ?humanGeneName ?orthologProtein ?orthologUniprot
    # WHERE {
    #   # Retrieve human genes associated with cancer from UniProt
    #   ?humanUniprot a up:Protein ;
    #               up:organism taxon:9606 ;
    #               up:encodedBy ?gene ;
    #               up:annotation ?annotation .
    #   ?annotation a up:Disease_Annotation ;
    #               rdfs:comment ?diseaseComment .
    #   FILTER(CONTAINS(LCASE(?diseaseComment), "cancer"))
    #   ?gene skos:prefLabel ?humanGeneName .
    #   # Find orthologs of these genes using OMA
    #   SERVICE <https://sparql.omabrowser.org/sparql> {
    #     ?cluster a orth:OrthologsCluster ;
    #       orth:hasHomologousMember ?node1 ;
    #       orth:hasHomologousMember ?node2 .
    #     ?node1 orth:hasHomologousMember* ?humanProtein .
    #     ?node2 orth:hasHomologousMember* ?orthologProtein .
    #     ?humanProtein lscr:xrefUniprot ?humanUniprot .
    #     ?orthologProtein lscr:xrefUniprot ?orthologUniprot .
    #     FILTER(?node1 != ?node2)
    #   } } LIMIT 10""",
    #     },
    # List human genes that have known orthologs in the rat and are expressed in the brain?
    # Which are the human genes associated with cancer and their orthologs expressed in the rat brain?
    # Find all proteins linked to arachidonate (CHEBI:32395) and their associated pathways
    # List all enzymes that have been experimentally validated and are involved in DNA repair
    # Find all proteins that have a mutagenesis annotation affecting their active site
    #     {
    #         # Way too slow for some reason
    #         "question": "Retrieve all proteins that are associated with Alzheimer disease. Return ?proteinURI, ?proteinLabel, ?diseaseURI, ?diseaseLabel, limit to 20",
    #         "endpoint": "https://sparql.uniprot.org/sparql/",
    #         "query": """PREFIX up: <http://purl.uniprot.org/core/>
    # PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    # SELECT ?proteinURI ?proteinLabel ?diseaseURI ?diseaseLabel
    # WHERE {
    #     ?proteinURI a up:Protein ;
    #             up:annotation ?diseaseAnnotation ;
    #             up:recommendedName/up:fullName ?proteinLabel .
    #     ?diseaseAnnotation up:disease ?diseaseURI .
    #     ?diseaseURI skos:prefLabel ?diseaseLabel .
    #     FILTER(CONTAINS(LCASE(?diseaseLabel), "alzheimer"))
    # } LIMIT 10""",
    #     },
    #     {
    #         # Always failing the connection between OMA and Bgee
    #         "question": "For protein Q9Y2T1, what are the orthologs in rats for genes expressed in the brain? Return ?ratProtein ?ratUniProtXref",
    #         "endpoint": "https://sparql.omabrowser.org/sparql/",
    #         "query": """PREFIX up: <http://purl.uniprot.org/core/>
    # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    # PREFIX orth: <http://purl.org/net/orth#>
    # PREFIX lscr: <http://purl.org/lscr#>
    # PREFIX obo: <http://purl.obolibrary.org/obo/>
    # SELECT DISTINCT ?ratProtein ?ratUniProtXref
    # WHERE {
    #     ?cluster a orth:OrthologsCluster.
    #     ?cluster orth:hasHomologousMember ?node1.
    #     ?cluster orth:hasHomologousMember ?node2.
    #     ?node1 orth:hasHomologousMember* ?humanProtein.
    #     ?node2 orth:hasHomologousMember* ?ratProtein.
    #     ?humanProtein a orth:Protein;
    #         lscr:xrefUniprot <http://purl.uniprot.org/uniprot/Q9Y2T1>.
    #     ?ratProtein a orth:Protein;
    #         orth:organism/obo:RO_0002162/up:scientificName 'Rattus norvegicus';
    #         lscr:xrefUniprot ?ratUniProtXref.
    #     FILTER(?node1 != ?node2)
    # }""",
    #     },
    #     {
    #         # It's making up URIs for photosynthesis instead of filtering on label
    #         "question": "Find all proteins that have a known 3D structure and are involved in photosynthesis. Return ?protein, ?structure, ?keywordLabel, limit to 20",
    #         "endpoint": "https://sparql.uniprot.org/sparql/",
    #         "query": """PREFIX up: <http://purl.uniprot.org/core/>
    # PREFIX keywords: <http://purl.uniprot.org/keywords/>
    # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    # SELECT DISTINCT ?protein ?structure ?keywordLabel
    # WHERE {
    #     ?protein a up:Protein ;
    #         up:classifiedWith/rdfs:label ?keywordLabel ;
    #         rdfs:seeAlso ?structure .
    #     ?structure up:database ?db .
    #     ?db up:category '3D structure databases' .
    #     FILTER(LCASE(?keywordLabel) = "photosynthesis")
    # } LIMIT 20""",
    #     },
    # {
    #     # Asking for "full name" will cause the RAG to fail, but validation don't catch it yet because VoID don't register the class when we have
    #     # we need to wait for LinkSet to be added to VoID in UniProt
    #     # Why not using "up:Protein up:enzyme ??"... Also up:enzymeClass never shows up in the relevant documents
    #         "question": "How can I get a list of proteins that are enzymes with their enzyme class? Return the ?proteinURI, ?enzymeClassURI, ?enzymeClassName, limit to 20",
    #         "endpoint": "https://sparql.uniprot.org/sparql/",
    #         "query": """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    #     PREFIX up: <http://purl.uniprot.org/core/>
    #     PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    #     SELECT ?proteinURI ?enzymeClassURI ?enzymeClassName
    #     WHERE {
    #        ?proteinURI a up:Protein ;
    #                    up:enzyme ?enzymeClassURI .
    #        ?enzymeClassURI skos:prefLabel ?enzymeClassName .
    #     #   ?protein a up:Protein ;
    #     #            up:annotation ?enzymeAnnotation .
    #     #   ?enzymeAnnotation a up:Catalytic_Activity_Annotation ;
    #     #                     up:catalyticActivity ?enzymeActivity .
    #     #   ?enzymeActivity up:enzymeClass ?enzymeClassURI .
    #     #   ?enzymeClassURI skos:prefLabel ?enzymeClassName .
    #     } LIMIT 20""",
    # },
    # Which are the human genes associated with lung cancer and their orthologs expressed in the rat brain?
    # {
    #     "question": "Which are the human genes associated with cancer (which have cancer in their disease label) and their orthologs expressed in the rat brain? Return the disease label, human gene URI, human gene HGNC symbol, ortholog rat gene URI",
    #     "endpoint": "https://sparql.uniprot.org/sparql/",
    #     "query": """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    # PREFIX up:<http://purl.uniprot.org/core/>
    # PREFIX taxon:<http://purl.uniprot.org/taxonomy/>
    # PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
    # PREFIX orth:<http://purl.org/net/orth#>
    # PREFIX dcterms:<http://purl.org/dc/terms/>
    # PREFIX obo:<http://purl.obolibrary.org/obo/>
    # PREFIX lscr:<http://purl.org/lscr#>
    # PREFIX genex:<http://purl.org/genex#>
    # PREFIX sio: <http://semanticscience.org/resource/>
    # SELECT DISTINCT ?diseaseLabel ?humanProtein ?hgncSymbol ?orthologRatProtein ?orthologRatGene
    # WHERE {
    # SERVICE <https://sparql.uniprot.org/sparql> {
    #     SELECT DISTINCT * WHERE {
    #     ?humanProtein a up:Protein ;
    #         up:organism/up:scientificName 'Homo sapiens' ;
    #         up:annotation ?annotation ;
    #         rdfs:seeAlso ?hgnc .
    #     ?hgnc up:database <http://purl.uniprot.org/database/HGNC> ;
    #         rdfs:comment ?hgncSymbol .
    #     ?annotation a up:Disease_Annotation ;
    #             up:disease ?disease .
    #     ?disease skos:prefLabel ?diseaseLabel.
    #     FILTER CONTAINS (?diseaseLabel, "cancer")
    #     }
    # }
    # SERVICE <https://sparql.omabrowser.org/sparql/> {
    #     SELECT ?humanProtein ?orthologRatProtein ?orthologRatGene WHERE {
    #     ?humanProteinOma a orth:Protein ;
    #             lscr:xrefUniprot ?humanProtein .
    #     ?orthologRatProtein a orth:Protein ;
    #         sio:SIO_010079 ?orthologRatGene ;
    #         orth:organism/obo:RO_0002162/up:scientificName 'Rattus norvegicus' .
    #     ?cluster a orth:OrthologsCluster .
    #     ?cluster orth:hasHomologousMember ?node1 .
    #     ?cluster orth:hasHomologousMember ?node2 .
    #     ?node1 orth:hasHomologousMember* ?humanProteinOma .
    #     ?node2 orth:hasHomologousMember* ?orthologRatProtein .
    #     FILTER(?node1 != ?node2)
    #     }
    # }
    # SERVICE <https://www.bgee.org/sparql/> {
    #     ?orthologRatGene genex:isExpressedIn ?anatEntity ;
    #         orth:organism ?ratOrganism .
    #     ?anatEntity rdfs:label 'brain' .
    #     ?ratOrganism obo:RO_0002162 taxon:10116 .
    # }
    # }""",
    # },
]


def result_sets_are_same(gen_set, ref_set) -> bool:
    """Check if all items from ref_set have equivalent items in gen_set, ignoring variable names"""
    # return all(ref_item in list(gen_set) for ref_item in list(ref_set))
    if not ref_set or not gen_set:
        # If either set is empty, they're the same only if both are empty
        return len(ref_set) == len(gen_set) == 0
    # Extract just the values from each binding, ignoring the variable names
    ref_values_set = []
    for ref_binding in ref_set:
        # Create a sorted tuple of values from each binding
        binding_values = tuple(sorted([v["value"] for v in ref_binding.values()]))
        ref_values_set.append(binding_values)
    gen_values_set = []
    for gen_binding in gen_set:
        binding_values = tuple(sorted([v["value"] for v in gen_binding.values()]))
        gen_values_set.append(binding_values)
    # Check if all reference values are present in generated values
    return all(ref_values in gen_values_set for ref_values in ref_values_set)

    # print(gen_set, ref_set)
    # for ref_item in ref_set:
    #     if ref_item not in gen_set:
    #         # logger.info(f"> Missing from generated: {ref_item}")
    #         return False
    # return True

    # gen_set, ref_set = list(gen_set), list(ref_set)
    # for item in gen_set:
    #     if item not in ref_set:
    #         # logger.info(f"> Missing from reference: {item}")
    #         return False
    # return all(item in gen_set for item in ref_set)


# QLEVER_UNIPROT = "https://qlever.cs.uni-freiburg.de/api/uniprot"

# Price per million tokens, open source models based on fireworks.io pricing
# https://openai.com/api/pricing/
# https://fireworks.ai/pricing
models = {
    # "Llama3.1 8B": {
    #     "id": "hf:meta-llama/Meta-Llama-3.1-8B-Instruct",
    #     "price_input": 0.2,
    #     "price_output": 0.2,
    # },
    # "Mixtral 8x22B": {
    #     "id": "hf:mistralai/Mixtral-8x22B-Instruct-v0.1",
    #     "price_input": 1.20,
    #     "price_output": 1.20,
    # },
    # "o3-mini": {
    #     "id": "openai/o3-mini",
    #     "price_input": 1.1,
    #     "price_output": 4.4,
    # },
    # Before adding extraction step: 🎯 RAG with validation - Success: 27, Different results: 9, No results: 4, Error: 2
    # After adding extraction
    # 🎯 RAG without validation - Success: 27, Different results: 11, No results: 2, Error: 8
    # 🎯 RAG with validation - Success: 31, Different results: 10, No results: 4, Error: 3
    # Price before fixing the token_usage gathering: 0.01421
    "gpt-4o": {
        "id": "openai/gpt-4o",
        "price_input": 5,
        "price_output": 15,
    },
    # # 🎯 RAG with validation - Success: 32, Different results: 7, No results: 3, Error: 0
    # "gpt-4o-mini": {
    #     "id": "openai/gpt-4o-mini",
    #     "price_input": 0.15,
    #     "price_output": 0.6,
    # },
}


def answer_no_rag(question: str, model: str):
    client = load_chat_model(Configuration(model=model))
    response = client.invoke(
        [
            SystemMessage(content=RESOLUTION_PROMPT),
            HumanMessage(content=question),
        ]
    )
    response = response.model_dump()
    response["messages"] = [
        {
            "content": response["content"],
            "response_metadata": response["response_metadata"],
        }
    ]
    return response


def answer_rag_without_validation(question: str, model: str):
    response = httpx.post(
        "http://localhost:8000/chat",
        headers={"Authorization": f"Bearer {settings.chat_api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
            "validate_output": False,
        },
        timeout=120,
        follow_redirects=True,
    )
    return response.json()


def answer_rag_with_validation(question: str, model: str):
    response = httpx.post(
        "http://localhost:8000/chat",
        headers={"Authorization": f"Bearer {settings.chat_api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
            "validate_output": True,
        },
        timeout=120,
        follow_redirects=True,
    )
    return response.json()


list_of_approaches = {
    "No RAG": answer_no_rag,
    "RAG without validation": answer_rag_without_validation,
    "RAG with validation": answer_rag_with_validation,
}

results_data = {
    "Model": [],
    "RAG Approach": [],
    "Success": [],
    "Different Results": [],
    "No Results": [],
    "Errors": [],
    "Price": [],
    # 'Precision': [],
    # "Recall": [],
    "F1": [],
}

number_of_tries = 3
start_time = time.time()

logger.info(
    f"🧪 Testing {len(example_queries)} queries using {settings.default_number_of_retrieved_docs} retrieved docs\n"
)
logger.info("## Executing references queries\n")

# Get results for the reference queries first
ref_results = []
for i, test_query in enumerate(example_queries):
    res_ref_finally_pass = False
    while not res_ref_finally_pass:
        try:
            query_start_time = time.time()
            res_from_ref = query_sparql(test_query["query"], test_query["endpoint"], timeout=300)["results"]["bindings"]
            logger.info(
                f"- [x] Reference query {i} '{test_query['question']}' took {time.time() - query_start_time:.2f} seconds"
            )
            ref_results.append(res_from_ref)
            res_ref_finally_pass = True
        except Exception as e:
            logger.info(f"- [ ] Timeout for reference query {i}: {e}, Trying again because we know it should work.")
            res_ref_finally_pass = False
    # res_from_ref = query_sparql(test_query["query"], QLEVER_UNIPROT)["results"]["bindings"]


for model_label, model in models.items():
    logger.info(f"\n## 🧠 Testing model {model_label}\n")
    res = defaultdict(dict)
    # e.g. res["No RAG"]["success"] += 1
    for approach in list_of_approaches:
        res[approach] = defaultdict(int)

    for query_num, test_query in enumerate(example_queries):
        for approach, approach_func in list_of_approaches.items():
            # logger.info(f"Approach {approach}")
            for t in range(number_of_tries):
                response = approach_func(test_query["question"], model["id"])
                # logger.info(response)
                chat_resp_md = response["messages"][-1]["content"]
                # chat_resp_md = response["choices"][0]["message"]["content"]
                # TODO: loop over all messages to get the total token usage in case of multiple messages (fix by calling LLM)
                for msg in response["messages"]:
                    # Retrieve token usage for all messages in the response
                    if "response_metadata" in msg and "token_usage" in msg["response_metadata"]:
                        res[approach]["input_tokens"] += msg["response_metadata"]["token_usage"]["prompt_tokens"]
                        res[approach]["output_tokens"] += msg["response_metadata"]["token_usage"]["completion_tokens"]
                        # res[approach]["input_tokens"] += response["messages"][-1]["response_metadata"]["token_usage"]["  prompt_tokens"]
                        # res[approach]["output_tokens"] += response["messages"][-1]["response_metadata"]["token_usage"]["completion_tokens"]
                        # print(chat_resp_md)
                try:
                    generated_sparqls = extract_sparql_queries(chat_resp_md)
                    if len(generated_sparqls) == 0:
                        raise Exception(f"No SPARQL query could be extracted from {chat_resp_md}")
                    generated_sparql = generated_sparqls[-1]
                    if generated_sparql["query"].strip() == test_query["query"].strip():
                        logger.info(f"✅ {t + 1}/{number_of_tries} {test_query['question']}. EXACT MATCH\n")
                        res[approach]["success"] += 1
                        continue

                    # Execute the generated query
                    res_from_generated = query_sparql(
                        generated_sparql["query"],
                        generated_sparql["endpoint_url"],
                        timeout=300,
                    )["results"]["bindings"]
                    # res_from_generated = query_sparql(generated_sparql["query"], QLEVER_UNIPROT)["results"]["bindings"]

                    if not result_sets_are_same(res_from_generated, ref_results[query_num]):
                        if len(res_from_generated) == 0:
                            res[approach]["no_results"] += 1
                        else:
                            res[approach]["different_results"] += 1
                        raise Exception(
                            f"\nResults mismatch. Ref: {len(ref_results[query_num])} != gen: {len(res_from_generated)}\n"
                        )
                    else:
                        logger.info(
                            f"✅ {t + 1}/{number_of_tries} {test_query['question']} = {len(res_from_generated)}\n"
                        )
                        res[approach]["success"] += 1

                except Exception as e:
                    res[approach]["fail"] += 1
                    if approach == "RAG with validation":
                        logger.info(f"❌ {t + 1}/{number_of_tries} {test_query['question']}\n{e}\n")
                        logger.info(f"```sparql\n{generated_sparql['query']}\n```\n")
                        logger.info("Correct query:\n")
                        logger.info(f"```sparql\n{test_query['query']}\n```\n")

        for approach in list_of_approaches:
            logger.info(
                f"🎯 {approach} - Success: {res[approach]['success']}, Different results: {res[approach]['different_results']}, No results: {res[approach]['no_results']}, Error: {res[approach]['fail'] - res[approach]['no_results'] - res[approach]['different_results']}\n"
            )

    for approach, result_row in res.items():
        mean_price = (
            (result_row["input_tokens"] * model["price_input"] / 1000000)
            + (result_row["output_tokens"] * model["price_output"] / 1000000)
        ) / (len(example_queries) * number_of_tries)
        precision = result_row["success"] / (result_row["success"] + result_row["fail"])
        recall = result_row["success"] / (result_row["success"] + result_row["fail"] - result_row["different_results"])
        results_data["Model"].append(model_label)
        results_data["RAG Approach"].append(approach)
        results_data["Success"].append(result_row["success"])
        results_data["Different Results"].append(result_row["different_results"])
        results_data["No Results"].append(result_row["no_results"])
        results_data["Errors"].append(result_row["fail"] - result_row["no_results"] - result_row["different_results"])
        results_data["Price"].append(round(mean_price, 5))
        # results_data['Precision'].append(precision)
        # results_data['Recall'].append(recall)
        if precision + recall == 0:
            results_data["F1"].append(0)
        else:
            results_data["F1"].append(round(2 * (precision * recall) / (precision + recall), 2))

logger.info("## Results\n")

df = pd.DataFrame(results_data)
logger.info(df)
logger.info("\n\n")
logger.info(df.to_csv(os.path.join(bench_folder, f"{file_time_prefix}_tests_results.csv"), index=False))

# Output Latex table
# latex_str = ""
# prev_model = next(iter(models.keys()))
# for _index, row in df.iterrows():
#     row_str = " & ".join(
#         [str(item) for item in row]
#     )  # Join all values in the row with " & "
#     row_str += " \\\\"
#     if row["Model"] != prev_model:
#         latex_str += "\\midrule\n"
#         prev_model = row["Model"]
#     latex_str += row_str + "\n"
# with open(
#     os.path.join(bench_folder, f"{file_time_prefix}_tests_results_latex.txt"), "w"
# ) as f:
#     f.write(latex_str)


logger.info(f"⏱️ Total runtime: {(time.time() - start_time) / 60:.2f} minutes")
