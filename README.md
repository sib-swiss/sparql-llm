<div align="center">

# ✨ SPARQL query generation with LLMs 🦜

[![PyPI - Version](https://img.shields.io/pypi/v/sparql-llm.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sparql-llm.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

This project provides tools to enhance the capabilities of Large Language Models (LLMs) in generating [SPARQL](https://www.w3.org/TR/sparql11-overview/) queries for specific endpoints:

- reusable components in `packages/sparql-llm` and published as the [`sparql-llm`](https://pypi.org/project/sparql-llm/) pip package
- a complete chat web service in `packages/expasy-agent`

The system integrates Retrieval-Augmented Generation (RAG) and SPARQL query validation through endpoint schemas, to ensure more accurate and relevant query generation on large scale knowledge graphs.

The components are designed to work either independently or as part of a full chat-based system that can be deployed for a set of SPARQL endpoints. It **requires endpoints to include metadata** such as [SPARQL query examples](https://github.com/sib-swiss/sparql-examples) and endpoint descriptions using the [Vocabulary of Interlinked Datasets (VoID)](https://www.w3.org/TR/void/), which can be automatically generated using the [void-generator](https://github.com/JervenBolleman/void-generator).

## 🌈 Features

- **Metadata Extraction**: Functions to extract and load relevant metadata from SPARQL endpoints. These loaders are compatible with [LangChain](https://python.langchain.com) but are flexible enough to be used independently, providing metadata as JSON for custom vector store integration.
- **SPARQL Query Validation**: A function to automatically parse and validate federated SPARQL queries against the VoID description of the target endpoints.
- **Deployable Chat System**: A reusable and containerized system for deploying an LLM-based chat service with a web UI, API, and vector database. This system helps users write SPARQL queries by leveraging endpoint metadata (WIP).
- **Live Example**: Configuration for **[chat.expasy.org](https://chat.expasy.org)**, an LLM-powered chat system supporting SPARQL query generation for endpoints maintained by the [SIB](https://www.sib.swiss/).

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

> Refer to the [LangChain documentation](https://python.langchain.com/v0.2/docs/) to figure out how to best integrate documents loaders to your stack.

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

> Checkout the [CONTRIBUTING.md](https://github.com/sib-swiss/sparql-llm/blob/main/CONTRIBUTING.md) page for more details on how to run the `sparql-llm` package in development and make a contribution.

## 🚀 Complete chat system

> [!WARNING]
>
> To deploy the complete chat system right now you will need to fork/clone this repository, change the configuration in `packages/expasy-agent/src/expasy_agent/config.py` and `compose.yml`, then deploy with docker/podman compose.
>
> It can easily be adapted to use any LLM served through an OpenAI-compatible API. We plan to make configuration and deployment of complete SPARQL LLM chat system easier in the future, let us know if you are interested in the GitHub issues!

Requirements: Docker, nodejs (to build the frontend), and optionally [`uv`](https://docs.astral.sh/uv/getting-started/installation/) if you want to run scripts outside of docker.

1. Explore and change the system configuration in `packages/expasy-agent/src/expasy_agent/config.py`

2. Create a `.env` file at the root of the repository to provide secrets and API keys:

   ```sh
   CHAT_API_KEY=NOT_SO_SECRET_API_KEY_USED_BY_FRONTEND_TO_AVOID_SPAM_FROM_CRAWLERS
   LOGS_API_KEY=SECRET_PASSWORD_TO_EASILY_ACCESS_LOGS_THROUGH_THE_API
   
   OPENAI_API_KEY=sk-proj-YYY
   GROQ_API_KEY=gsk_YYY
   HUGGINGFACEHUB_API_TOKEN=
   TOGETHER_API_KEY=
   DEEPSEEK_API_KEY=
   
   GLHF_API_KEY=glhf_43fb9eb000f0c3d93be7c57cf30edf4d
   AZURE_INFERENCE_CREDENTIAL=
   AZURE_INFERENCE_ENDPOINT=https://project-id.services.ai.azure.com/models
   
   LANGSMITH_PROJECT=expasy-agent
   LANGSMITH_API_KEY=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
   
   ```

3. Build the chat UI webpage:

   ```sh
   cd chat-with-context
   npm i
   npm run build:demo
   cd ..
   ```

4. **Start** the vector database and web server locally for development, with code from the `packages` folder mounted in the container and automatic API reload on changes to the code:

   ```bash
   docker compose -f compose.dev.yml up
   ```

   * Chat web UI available at http://localhost:8000
   * OpenAPI Swagger UI available at http://localhost:8000/docs
   * Vector database dashboard UI available at http://localhost:6333/dashboard

   In production, you will need to make some changes to the `compose.yml` file to adapt it to your server/proxy setup:

   ```bash
   docker compose up
   ```

   > All data from the containers are stored persistently in the `data` folder (e.g. vectordb indexes)

5. When the stack is up you can run the script to **index** the SPARQL endpoints from within the container (need to do it once):

   ```sh
   docker compose exec api uv run src/expasy_agent/indexing/index_endpoints.py
   ```

> [!WARNING]
>
> **Experimental entities indexing**: it can take a lot of time to generate embeddings for millions of entities. So we recommend to run the script to generate embeddings on a machine with GPU (does not need to be a powerful one, but at least with a GPU, checkout [fastembed GPU docs](https://qdrant.github.io/fastembed/examples/FastEmbed_GPU/) to install the GPU drivers and dependencies)
>
> ```sh
> docker compose -f compose.dev.yml up vectordb -d
> cd packages/expasy-agent
> VECTORDB_URL=http://localhost:6334 nohup uv run --extra gpu src/expasy_agent/indexing/index_entities.py --gpu &
> ```
>
> Then move the entities collection containing the embeddings in `data/qdrant/collections/entities` before starting the stack

There is a benchmarking scripts for the system that will run a list of questions and compare their results to a reference SPARQL queries, with and without query validation, against a list of LLM providers. You will need to change the list of queries if you want to use it for different endpoints. You will need to start the stack in development mode to run it:

```sh
uv run packages/expasy-agent/tests/benchmark.py
```

> It takes time to run and will log the output and results in `data/benchmarks`

## 🪶 How to cite this work

If you reuse any part of this work, please cite [the arXiv paper](https://arxiv.org/abs/2410.06062):

```
@misc{emonet2024llmbasedsparqlquerygeneration,
    title={LLM-based SPARQL Query Generation from Natural Language over Federated Knowledge Graphs},
    author={Vincent Emonet and Jerven Bolleman and Severine Duvaud and Tarcisio Mendes de Farias and Ana Claudia Sima},
    year={2024},
    eprint={2410.06062},
    archivePrefix={arXiv},
    primaryClass={cs.DB},
    url={https://arxiv.org/abs/2410.06062},
}
```

