<div align="center">

# 🦜✨ SPARQL query generation with LLMs

[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

Reusable components and complete web service to improve Large Language Models (LLMs) capabilities when generating [SPARQL](https://www.w3.org/TR/sparql11-overview/) queries for a given set of endpoints, using Retrieval-Augmented Generation (RAG) and SPARQL query validation from the endpoints schemas.

The different components of the system can be used separately, or the whole chat system can be deployed for a set of endpoints. It relies on the endpoint containing some descriptive metadata: [SPARQL query examples](https://github.com/sib-swiss/sparql-examples), and endpoint description using the [Vocabulary of Interlinked Datasets (VoID)](https://www.w3.org/TR/void/), which can generated automatically using the [void-generator](https://github.com/JervenBolleman/void-generator).

This repository contains:

* Functions to extract and load relevant metadata from a SPARQL endpoints. Loaders are compatible with [LangChain](https://python.langchain.com), but they can also be used outside of LangChain as they just return a list of documents with metadata as JSON, which can then be loaded how you want in your vectorstore.
* Function to automatically parse and validate SPARQL queries based on an endpoint VoID description.
* A complete reusable system to deploy a LLM chat system with web UI, API and vector database, designed to help users to write SPARQL queries for a given set of endpoints by exploiting metadata uploaded to the endpoints (WIP).
* The deployment configuration for **[chat.expasy.org](https://chat.expasy.org)** the LLM chat system to help users accessing the endpoints maintained at the [SIB](https://www.sib.swiss/).

> [!TIP]
>
> You can quickly check if an endpoint contains the expected metadata at [sib-swiss.github.io/sparql-editor/check](https://sib-swiss.github.io/sparql-editor/check)

## 🪄 Reusable components

### Installation

This package requires Python >=3.9, install it from the git repository with:

```bash
pip install sparql-llm
```

### SPARQL query examples loader

Load SPARQL query examples defined using the SHACL ontology from a SPARQL endpoint. See **[github.com/sib-swiss/sparql-examples](https://github.com/sib-swiss/sparql-examples)** for more details on how to define the examples.

```python
from sparql_llm import SparqlExamplesLoader

loader = SparqlExamplesLoader("https://sparql.uniprot.org/sparql/")
docs = loader.load()
print(len(docs))
print(docs[0].metadata)
```

> Refer to the [LangChain documentation](https://python.langchain.com/v0.2/docs/) to figure out how to best integrate documents loaders to your stack.

### SPARQL endpoint schema loader

Generate a human-readable schema using the ShEx format to describe all classes of a SPARQL endpoint based on the [VoID description](https://www.w3.org/TR/void/) present in the endpoint. Ideally the endpoint should also contain the ontology describing the class, so the `rdfs:label` and `rdfs:comment` of the classes can be used to generate embeddings and improve semantic matching.

> [!TIP]
>
> Checkout the **[void-generator](https://github.com/JervenBolleman/void-generator)** project to automatically generate VoID description for your endpoint.

```python
from sparql_llm import SparqlVoidShapesLoader

loader = SparqlVoidShapesLoader("https://sparql.uniprot.org/sparql/")
docs = loader.load()
print(len(docs))
print(docs[0].metadata)
```

> The generated shapes are well-suited for use with a LLM or a human, as they provide clear information about which predicates are available for a class, and the corresponding classes or datatypes those predicates point to. Each object property references a list of classes rather than another shape, making each shape self-contained and interpretable on its own, e.g. for a *Disease Annotation* in UniProt:
>
> ```turtle
> up:Disease_Annotation {
>   a [ up:Disease_Annotation ] ;
>   up:sequence [ up:Chain_Annotation up:Modified_Sequence ] ;
>   rdfs:comment xsd:string ;
>   up:disease IRI
> }
> ```

### Generate complete ShEx shapes from VoID description

You can also generate the complete ShEx shapes for a SPARQL endpoint with:

```python
from sparql_llm import get_shex_from_void

shex_str = get_shex_from_void("https://sparql.uniprot.org/sparql/")
print(shex_str)
```

### Validate a SPARQL query based on VoID description

This takes a SPARQL query and validates the predicates/types used are compliant with the VoID description present in the SPARQL endpoint the query is executed on.

This function supports:

* federated queries (VoID description will be automatically retrieved for each SERVICE call in the query),
* path patterns (e.g. `orth:organism/obo:RO_0002162/up:scientificName`)

This function requires that at least one type is defined for each endpoint, but it will be able to infer types of subjects that are connected to the subject for which the type is defined.

It will return a list of issues described in natural language, with hints on how to fix them (by listing the available classes/predicates), which can be passed to an LLM as context to help it figuring out how to fix the query.

```python
from sparql_llm import validate_sparql_with_void

sparql_query = """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX orth: <http://purl.org/net/orth#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX lscr: <http://purl.org/lscr#>
PREFIX genex: <http://purl.org/genex#>
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
print("\n".join(issues))
```

## 🚀 Complete chat system

> [!WARNING]
>
> To deploy the complete chat system right now you will need to fork this repository, change the configuration in `src/sparql_llm/config.py` and `compose.yml`, then deploy with docker/podman compose.
>
> It can easily be adapted to use any LLM served through an OpenAI-compatible API. We plan to make configuration and deployment of complete SPARQL LLM chat system easier in the future, let us know if you are interested in the GitHub issues!

Create a `.env` file at the root of the repository to provide OpenAI API key to a `.env` file at the root of the repository:

```bash
OPENAI_API_KEY=sk-proj-YYY
GLHF_API_KEY=APIKEY_FOR_glhf.chat_USED_FOR_OPEN_SOURCE_MODELS
EXPASY_API_KEY=NOT_SO_SECRET_API_KEY_USED_BY_FRONTEND_TO_AVOID_SPAM_FROM_CRAWLERS
LOGS_API_KEY=PASSWORD_TO_EASILY_ACCESS_LOGS_THROUGH_THE_API
```

Start the web UI, API, and similarity search engine in production (you might need to make some changes to the `compose.yml` file to adapt it to your server/proxy setup):

```bash
docker compose up
```

Start the stack locally for development, with code from `src` folder mounted in the container and automatic API reload on changes to the code:

```bash
docker compose -f compose.dev.yml up
```

* Chat web UI available at http://localhost:8000
* OpenAPI Swagger UI available at http://localhost:8000/docs
* Vector database dashboard UI available at http://localhost:6333/dashboard
