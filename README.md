<div align="center">

# ✨ SPARQL query generation with LLMs 🦜

[![PyPI - Version](https://img.shields.io/pypi/v/sparql-llm.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sparql-llm.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

This project provides tools to enhance the capabilities of Large Language Models (LLMs) in generating [SPARQL](https://www.w3.org/TR/sparql11-overview/) queries for specific endpoints:

- a complete **chat web service** available at **[expasy.org/chat](https://expasy.org/chat)**
- a **MCP server** exposing tools at **[chat.expasy.org/mcp](https://chat.expasy.org/mcp)**
- **reusable components** published as the **[`sparql-llm`](https://pypi.org/project/sparql-llm/)** pip package

The system integrates Retrieval-Augmented Generation (RAG) and SPARQL query validation through endpoint schemas, to ensure more accurate and relevant query generation on large scale knowledge graphs.

The components are designed to work either independently or as part of a full chat-based system that can be deployed for a set of SPARQL endpoints. It **requires endpoints to include metadata** such as [SPARQL query examples](https://github.com/sib-swiss/sparql-examples) and endpoint descriptions using the [Vocabulary of Interlinked Datasets (VoID)](https://www.w3.org/TR/void/), which can be automatically generated using the [void-generator](https://github.com/JervenBolleman/void-generator).

## 🌈 Features

- **Metadata Extraction**: Functions to extract and load relevant metadata from SPARQL endpoints. These loaders are compatible with [LangChain](https://python.langchain.com) but are flexible enough to be used independently, providing metadata as JSON for custom vector store integration.
- **SPARQL Query Validation**: A function to automatically parse and validate federated SPARQL queries against the VoID description of the target endpoints.
- **MCP server** with tools to help LLM write SPARQL queries for a set of endpoints
- **Deployable Chat System**: A reusable and containerized system for deploying an LLM-based chat service with a web UI, API, and vector database. This system helps users write SPARQL queries by leveraging endpoint metadata (WIP).
- **Live Example**: Configuration for **[expasy.org/chat](https://expasy.org/chat)**, an LLM-powered chat system supporting SPARQL query generation for endpoints maintained by the [SIB](https://www.sib.swiss/).

> [!TIP]
>
> You can quickly check if an endpoint contains the expected metadata at [sib-swiss.github.io/sparql-editor/check](https://sib-swiss.github.io/sparql-editor/check)

## 🔌 MCP server

The server exposes a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) endpoint to access [biodata resources](https://www.expasy.org/) at the [SIB](https://www.sib.swiss/), through their [SPARQL](https://www.w3.org/TR/sparql12-query/) endpoints, such as UniProt, Bgee, OMA, SwissLipids, Cellosaurus at **[chat.expasy.org/mcp](https://chat.expasy.org/mcp)**

### 🛠️ Available tools

- **📝 Retrieve relevant documents** (query examples and classes schema) to help writing SPARQL queries to access SIB biodata resources
  - Arguments:
    - `question` (string): the user's question
    - `potential_classes` (list[string]): high level concepts and potential classes that could be found in the SPARQL endpoints
    - `steps` (list[string]): split the question in standalone smaller parts if relevant
- **🏷️ Retrieve relevant classes schema** to help writing SPARQL queries to access SIB biodata resources
  - Arguments:
    - `classes` (list[string]): high level concepts and potential classes that could be found in the SPARQL endpoints
- 📡  **Execute a SPARQL query** against a SPARQL endpoint
  - Arguments:
    - `query` (string): a valid SPARQL query string
    - `endpoint` (string): the SPARQL endpoint URL to execute the query against

### ⚡️ Connect client to MCP server

Follow the instructions of your client, and use the URL of the public server: **https://chat.expasy.org/mcp**

For example, for GitHub Copilot in VSCode, to add a new MCP server through the VSCode UI:

- [x] Open side panel chat (`ctrl+shift+i` or `cmd+shift+i`), and make sure the mode is set to `Agent` in the bottom right
- [x] Open command palette (`ctrl+shift+p` or `cmd+shift+p`), and search for `MCP: Open User Configuration`, this will open a `mcp.json` file

#### 📡 Use streamable HTTP server

Connect to a running streamable HTTP MCP server, such as the publicly available [chat.expasy.org/mcp](https://chat.expasy.org/mcp).

In your VSCode `mcp.json` you should have the following:

```sh
{
	"servers": {
		"expasy-mcp-http": {
			"url": "https://chat.expasy.org/mcp",
			"type": "http"
		}
	}
}
```

#### ⌨️ Use stdio transport

```sh
uvx sparql-llm
```

Optionally you can provide the path to a custom settings JSON file to configure the server (e.g. the list of endpoints that will be indexed and available through the server), see the [`Settings` class](https://github.com/sib-swiss/sparql-llm/blob/main/src/sparql_llm/config.py) for detailed available settings.

Example VSCode `mcp.json` file:

```json
{
  "servers": {
    "expasy-mcp": {
      "type": "stdio",
      "command": "uvx",
      "env": {
				"SETTINGS_FILEPATH": "~/dev/sparql-mcp.json"
			},
      "args": [
        "sparql-llm"
      ]
    }
  }
}
```

> [!IMPORTANT]
>
> Click on `Start` just on top of `"openroute-mcp"` to start the connection to the MCP server.
>
> You can click the wrench and screwdriver button 🛠️ (`Configure Tools...`) to enable/disable specific tools

> [!NOTE]
>
> More details available in [the VSCode MCP official docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers).

## 📦️ Reusable components

### Installation

> Requires Python >=3.10

```bash
pip install sparql-llm
```

Or with `uv`:

```sh
uv add sparql-llm
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

## 🚀 Complete chat system

> [!WARNING]
>
> To deploy the complete chat system right now you will need to fork/clone this repository, change the configuration in `src/sparql-llm/config.py` and `compose.yml`, then deploy with docker/podman compose. It can easily be adapted to use any LLM served through an OpenAI-compatible API.
>

Requirements: Docker, nodejs (to build the frontend), and optionally [`uv`](https://docs.astral.sh/uv/getting-started/installation/) if you want to run scripts outside of docker.

1. Explore and change the system configuration in `src/sparql-llm/config.py`

2. Create a `.env` file at the root of the repository to provide secrets and API keys:

   ```sh
   CHAT_API_KEY=NOT_SO_SECRET_API_KEY_USED_BY_FRONTEND_TO_AVOID_SPAM_FROM_CRAWLERS
   LOGS_API_KEY=SECRET_PASSWORD_TO_EASILY_ACCESS_LOGS_THROUGH_THE_API

   OPENROUTER_API_KEY=sk-YYY
   OPENAI_API_KEY=sk-proj-YYY

   LANGFUSE_HOST=https://cloud.langfuse.com
   LANGFUSE_PUBLIC_KEY=
   LANGFUSE_SECRET_KEY=
   ```

3. Optionally, if you made changes to it, build the chat UI webpage:

   ```sh
   cd chat-with-context
   npm i
   npm run build:demo
   cd ..
   ```

   > You can change the UI around the chat in `chat-with-context/demo/index.html`

4. **Start** the vector database and web server locally for development, with code from the `src` folder mounted in the container and automatic API reload on changes to the code:

   ```bash
   docker compose up
   ```

   * Chat web UI available at http://localhost:8000
   * OpenAPI Swagger UI available at http://localhost:8000/docs
   * Vector database dashboard UI available at http://localhost:6333/dashboard

   **In production**, you will need to make some changes to the `compose.prod.yml` file to adapt it to your server/proxy setup:

   ```bash
   docker compose -f compose.prod.yml up
   ```

   Then run the indexing script manually from within the container to index the SPARQL endpoints (need to do it once):

   ```sh
   docker compose -f compose.prod.yml exec api uv run src/sparql_llm/indexing/index_resources.py
   ```

   > All data from the containers are stored persistently in the `data` folder (e.g. vectordb indexes and endpoints metadata)

> [!NOTE]
>
> Query the chat API:
>
> ```sh
> curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"messages": [{"role": "user", "content": "What is the HGNC symbol for the P68871 protein?"}], "model": "mistralai/mistral-small-latest", "stream": true}'
> ```

> [!WARNING]
>
> **Experimental entities indexing**: it can take a lot of time to generate embeddings for millions of entities. So we recommend to run the script to generate embeddings on a machine with GPU (does not need to be a powerful one, but at least with a GPU, checkout [fastembed GPU docs](https://qdrant.github.io/fastembed/examples/FastEmbed_GPU/) to install the GPU drivers and dependencies)
>
> ```sh
> docker compose up vectordb -d
> VECTORDB_URL=http://localhost:6334 nohup uv run --extra gpu src/sparql_llm/indexing/index_entities.py --gpu &
> ```
>
>Then move the entities collection containing the embeddings in `data/qdrant/collections/entities` before starting the stack

### 🥇 Benchmarks

There are a few benchmarks available for the system:

- The `tests/benchmark.py` script will run a list of questions and compare their results to a reference SPARQL queries, with and without query validation, against a list of LLM providers. You will need to change the list of queries if you want to use it for different endpoints. You will need to start the stack in development mode to run it:

  ```sh
  uv run --env-file .env tests/benchmark.py
  ```

  > It takes time to run and will log the output and results in `data/benchmarks`

- Follow [these instructions](tests/text2sparql/README.md) to run the `Text2SPARQL Benchmark`.

- For biodata benchmark:

  ```sh
  docker compose up -d
  VECTORDB_URL=http://localhost:6334 uv run tests/benchmark_biodata.py
  ```

## 🧑‍🏫 Tutorial

There is a step by step tutorial to show how a LLM-based chat system for generating SPARQL queries can be easily built here: https://sib-swiss.github.io/sparql-llm

## 🧑‍💻 Contributing

Checkout the [`CONTRIBUTING.md`](https://github.com/sib-swiss/sparql-llm/blob/main/CONTRIBUTING.md) page.

## 🪶 How to cite this work

If you reuse any part of this work, please cite at least one of our articles below:

- [SPARQL-LLM: Real-Time SPARQL Query Generation from Natural Language Questions](https://arxiv.org/abs/2512.14277)
```bibtex
@misc{smeros2025sparqlllmrealtimesparqlquery,
      title={SPARQL-LLM: Real-Time SPARQL Query Generation from Natural Language Questions},
      author={Panayiotis Smeros and Vincent Emonet and Ruijie Wang and Ana-Claudia Sima and Tarcisio Mendes de Farias},
      year={2025},
      eprint={2512.14277},
      archivePrefix={arXiv},
      primaryClass={cs.IR},
      url={https://arxiv.org/abs/2512.14277},
}
```

- [LLM-based SPARQL Query Generation from Natural Language over Federated Knowledge Graphs](https://ceur-ws.org/Vol-3953/355.pdf)
```bibtex
@conference{emonet2025llm,
    title={LLM-based SPARQL Query Generation from Natural Language over Federated Knowledge Graphs},
    author={Emonet, Vincent and Bolleman, Jerven and Duvaud, Severine and Mendes de Farias, Tarcisio and Sima, Ana Claudia},
    year = 2025,
    note={CEUR-WS.org, online \url{https://ceur-ws.org/Vol-3953/355.pdf}},
    booktitle = {ISWC 2024 Special Session on Harmonising Generative AI and Semantic Web Technologies, November 13, 2024, Baltimore, Maryland},
    volume = 3953,
    series = {CEUR Workshop Proceedings},
}
```

<!-- mcp-name: io.github.sib-swiss/sparql-llm -->
