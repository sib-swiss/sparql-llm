# ✨ SPARQL query generation with LLMs 🦜

[![PyPI - Version](https://img.shields.io/pypi/v/sparql-llm.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sparql-llm.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

This project provides reusable components and functions to  enhance the capabilities of Large Language Models (LLMs) in generating [SPARQL](https://www.w3.org/TR/sparql11-overview/) queries for specific endpoints. By integrating Retrieval-Augmented  Generation (RAG) and SPARQL query validation through endpoint schemas,  it ensures more accurate and relevant query generation on large scale knowledge graphs.

The components are designed to work either independently or as part of a full chat-based system that can be deployed for a set of SPARQL endpoints. It **requires endpoints to include metadata** such as [SPARQL query examples](https://github.com/sib-swiss/sparql-examples) and endpoint descriptions using the [Vocabulary of Interlinked Datasets (VoID)](https://www.w3.org/TR/void/), which can be automatically generated using the [void-generator](https://github.com/JervenBolleman/void-generator).

## 🌈 Features

- **Metadata Extraction**: Functions to extract and load relevant metadata from SPARQL endpoints. These loaders are compatible with [LangChain](https://python.langchain.com) but are flexible enough to be used independently, providing metadata as JSON for custom vector store integration.
- **SPARQL Query Validation**: A function to automatically parse and validate federated SPARQL queries against the VoID description of the target endpoints.

> [!TIP]
>
> You can quickly check if an endpoint contains the expected metadata at [sib-swiss.github.io/sparql-editor/check](https://sib-swiss.github.io/sparql-editor/check)

## 📦️ Reusable components

### Installation

> Requires Python >=3.9

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

You can provide the examples as a file if it is not integrated in the endpoint, e.g.:

```python
loader = SparqlExamplesLoader("https://sparql.uniprot.org/sparql/", examples_file="uniprot_examples.ttl")
```

> Refer to the [LangChain documentation](https://python.langchain.com/v0.2/docs/) to figure out how to best integrate documents loaders to your system.

> [!NOTE]
>
> You can check the completeness of your examples against the endpoint schema using [this notebook](https://github.com/sib-swiss/sparql-llm/blob/main/notebooks/compare_queries_examples_to_void.ipynb).

### SPARQL endpoint schema loader

Generate a human-readable schema using the ShEx format to describe all classes of a SPARQL endpoint based on the [VoID description](https://www.w3.org/TR/void/) present in the endpoint. Ideally the endpoint should also contain the ontology describing the classes, so the `rdfs:label` and `rdfs:comment` of the classes can be used to generate embeddings and improve semantic matching.

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

You can provide the VoID description as a file if it is not integrated in the endpoint, e.g.:

```python
loader = SparqlVoidShapesLoader("https://sparql.uniprot.org/sparql/", void_file="uniprot_void.ttl")
```

> The generated shapes are well-suited for use with a LLM or a human, as they provide clear information about which predicates are available for a class, and the corresponding classes or datatypes those predicates point to. Each object property references a list of classes rather than another shape, making each shape self-contained and interpretable on its own, e.g. for a *Disease Annotation* in UniProt:
>
> ```turtle
> up:Disease_Annotation {
> a [ up:Disease_Annotation ] ;
> up:sequence [ up:Chain_Annotation up:Modified_Sequence ] ;
> rdfs:comment xsd:string ;
> up:disease IRI
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
        orth:organism/obo:RO_0002162/up:name 'Rattus norvegicus' .
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
```

## 🧑‍💻 Development

This section is for if you want to run the package and reusable components in development, and get involved by making a code contribution.

> Requirements: [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle scripts and virtual environments.

### 📥️ Clone

Clone the repository:

```bash
git clone https://github.com/sib-swiss/sparql-llm
cd sparql-llm
```

### ☑️ Run tests

Make sure the existing tests still work by running the test suite and linting checks. Note that any pull requests to the fairworkflows repository on github will automatically trigger running of the test suite;

```bash
cd packages/sparql-llm
uv run pytest
```

To display all logs when debugging:

```bash
uv run test -s
```

### 🧹 Format code

```bash
uvx ruff format
uvx ruff check --fix
```

### ♻️ Reset the environment

Upgrade `uv`:

```sh
uv self update
```

Clean `uv` cache:

```sh
uv cache clean
```

### 🏷️ New release process

Get a PyPI API token at [pypi.org/manage/account](https://pypi.org/manage/account).

1. Increment the `version` number in the `pyproject.toml` file.

   ```bash
   uvx hatch version fix
   ```

2. Build and publish:

   ```bash
   uv build
   cd ../..
   uv publish
   ```

> If `uv publish` is still broken:
>
> ```sh
> uvx hatch build
> uvx hatch publish
> ```
