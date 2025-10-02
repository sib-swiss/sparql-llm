<div align="center">

# ✨ SPARQL query generation with LLMs 🦜

[![PyPI - Version](https://img.shields.io/pypi/v/sparql-llm.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sparql-llm.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

This project provides tools to enhance the capabilities of Large Language Models (LLMs) in generating [SPARQL](https://www.w3.org/TR/sparql11-overview/) queries for specific endpoints:

- reusable components in `src/sparql-llm` and published as the [`sparql-llm`](https://pypi.org/project/sparql-llm/) pip package
- a MCP server to expose tools to help LLM write SPARQL queries for a set of endpoints
- a complete chat web service in `src/expasy-agent`
- an experimental MCP server to generate and execute SPARQL queries on SIB resources in `src/expasy-mcp`

The system integrates Retrieval-Augmented Generation (RAG) and SPARQL query validation through endpoint schemas, to ensure more accurate and relevant query generation on large scale knowledge graphs.

The components are designed to work either independently or as part of a full chat-based system that can be deployed for a set of SPARQL endpoints. It **requires endpoints to include metadata** such as [SPARQL query examples](https://github.com/sib-swiss/sparql-examples) and endpoint descriptions using the [Vocabulary of Interlinked Datasets (VoID)](https://www.w3.org/TR/void/), which can be automatically generated using the [void-generator](https://github.com/JervenBolleman/void-generator).

## 🌈 Features

- **Metadata Extraction**: Functions to extract and load relevant metadata from SPARQL endpoints. These loaders are compatible with [LangChain](https://python.langchain.com) but are flexible enough to be used independently, providing metadata as JSON for custom vector store integration.
- **SPARQL Query Validation**: A function to automatically parse and validate federated SPARQL queries against the VoID description of the target endpoints.
- **MCP server** with tools to help LLM write SPARQL queries for a set of endpoints
- **Deployable Chat System**: A reusable and containerized system for deploying an LLM-based chat service with a web UI, API, and vector database. This system helps users write SPARQL queries by leveraging endpoint metadata (WIP).
- **Live Example**: Configuration for **[chat.expasy.org](https://chat.expasy.org)**, an LLM-powered chat system supporting SPARQL query generation for endpoints maintained by the [SIB](https://www.sib.swiss/).

> [!TIP]
>
> You can quickly check if an endpoint contains the expected metadata at [sib-swiss.github.io/sparql-editor/check](https://sib-swiss.github.io/sparql-editor/check)

## 🔌 MCP server

The server exposes a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) endpoint to access [biodata resources](https://www.expasy.org/) at the [SIB](https://www.sib.swiss/), through their [SPARQL](https://www.w3.org/TR/sparql12-query/) endpoints, such as UniProt, Bgee, OMA, SwissLipids, Cellosaurus. Available tools are:

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

### 🐙 Connect client

Follow the instructions of your client, and use the `/mcp` URL of your deployed server (e.g. http://localhost:8000/mcp)

For example, for GitHub Copilot in VSCode, to add a new MCP server through the VSCode UI:

- [x] Open side panel chat (`ctrl+shift+i` or `cmd+shift+i`), and make sure the mode is set to `Agent` in the bottom right
- [x] Open command palette (`ctrl+shift+p` or `cmd+shift+p`), and search for `MCP: Open User Configuration`, this will open a `mcp.json` file

In VSCode `mcp.json` you should have the following:

```sh
{
	"servers": {
		"expasy-mcp-server": {
			"url": "http://localhost:8000/mcp",
			"type": "http"
		}
	},
	"inputs": []
}
```

You can click the wrench and screwdriver button 🛠️ (`Select Tools...`) to enable/disable specific tools

> [!NOTE]
>
> More details in [the official docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers).

## 📦️ Reusable components

Checkout the [`src/sparql-llm/README.md`](https://github.com/sib-swiss/sparql-llm/tree/main/src/sparql-llm) for more details on how to use the reusable components.

## 🧑‍🏫 Tutorial

There is a step by step tutorial to show how a LLM-based chat system for generating SPARQL queries can be easily built here: https://sib-swiss.github.io/sparql-llm

## 🚀 Complete chat system

> [!WARNING]
>
> To deploy the complete chat system right now you will need to fork/clone this repository, change the configuration in `src/expasy-agent/src/expasy_agent/config.py` and `compose.yml`, then deploy with docker/podman compose.
>
> It can easily be adapted to use any LLM served through an OpenAI-compatible API. We plan to make configuration and deployment of complete SPARQL LLM chat system easier in the future, let us know if you are interested in the GitHub issues!

Requirements: Docker, nodejs (to build the frontend), and optionally [`uv`](https://docs.astral.sh/uv/getting-started/installation/) if you want to run scripts outside of docker.

1. Explore and change the system configuration in `src/expasy-agent/src/expasy_agent/config.py`

2. Create a `.env` file at the root of the repository to provide secrets and API keys:

   ```sh
   CHAT_API_KEY=NOT_SO_SECRET_API_KEY_USED_BY_FRONTEND_TO_AVOID_SPAM_FROM_CRAWLERS
   LOGS_API_KEY=SECRET_PASSWORD_TO_EASILY_ACCESS_LOGS_THROUGH_THE_API

   OPENAI_API_KEY=sk-proj-YYY
   GROQ_API_KEY=gsk_YYY
   HUGGINGFACEHUB_API_TOKEN=
   TOGETHER_API_KEY=
   AZURE_INFERENCE_CREDENTIAL=
   AZURE_INFERENCE_ENDPOINT=https://project-id.services.ai.azure.com/models

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
   docker compose exec api uv run src/expasy_agent/indexing/index_resources.py
   ```

> [!WARNING]
>
> **Experimental entities indexing**: it can take a lot of time to generate embeddings for millions of entities. So we recommend to run the script to generate embeddings on a machine with GPU (does not need to be a powerful one, but at least with a GPU, checkout [fastembed GPU docs](https://qdrant.github.io/fastembed/examples/FastEmbed_GPU/) to install the GPU drivers and dependencies)
>
> ```sh
> docker compose -f compose.dev.yml up vectordb -d
> cd src/expasy-agent
> VECTORDB_URL=http://localhost:6334 nohup uv run --extra gpu src/expasy_agent/indexing/index_entities.py --gpu &
> ```
>
> Then move the entities collection containing the embeddings in `data/qdrant/collections/entities` before starting the stack

There is a benchmarking scripts for the system that will run a list of questions and compare their results to a reference SPARQL queries, with and without query validation, against a list of LLM providers. You will need to change the list of queries if you want to use it for different endpoints. You will need to start the stack in development mode to run it:

```sh
uv run --env-file .env src/expasy-agent/tests/benchmark.py
```

> It takes time to run and will log the output and results in `data/benchmarks`

Follow [these instructions](src/expasy-agent/tests/text2sparql/README.md) to run the `Text2SPARQL Benchmark`.

## 🪶 How to cite this work

If you reuse any part of this work, please cite [the arXiv paper](https://arxiv.org/abs/2410.06062):

```bibtex
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
