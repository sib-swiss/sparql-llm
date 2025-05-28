# 🧬 SIB SPARQL BioData MCP server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server to access [biodata resources](https://www.expasy.org/) at the [SIB](https://www.sib.swiss/), through their [SPARQL](https://www.w3.org/TR/sparql12-query/) endpoints, such as UniProt, Bgee, OMA, SwissLipids, Cellosaurus.

## 🪄 Available tools

- 📝 Help users to **write SPARQL queries** to access SIB biodata resources
  - Arguments:
    - `question` (string): the user's question
    - `potential_classes` (list[string]): high level concepts and potential classes that could be found in the SPARQL endpoints
    - `steps` (list[string]): split the question in standalone smaller parts if relevant
- 📡  **Execute a SPARQL query** against a SPARQL endpoint
  - Arguments:
    - `query` (string): a valid SPARQL query string
    - `endpoint` (string): the SPARQL endpoint URL to execute the query against

## 🔌 Connect client

Follow the instructions of your client, and use the `/sse` URL of your deployed server (e.g. http://127.0.0.1:8888/sse)

### 🐙 VSCode GitHub Copilot

Add a new MCP server through the VSCode UI:

- [x] Open side panel chat (`ctrl+shift+i` or `cmd+shift+i`), and make sure the mode is set to `Agent` in the bottom right
- [x] Click the wrench and screwdriver button 🛠️ (`Select Tools...`)
- [x] Click `Add MCP server...`: provide the URL to the MCP server, by default http://127.0.0.1:8888/sse

In VSCode `settings.json` you should have the following:

```sh
		"chat.agent.enabled": true,
    "chat.mcp.enabled": true,
    "mcp": {
        "servers": {
            "expasy-mcp": {
                "type": "sse",
                "url": "http://127.0.0.1:8888/sse"
            }
        }
    }
```

> [!NOTE]
>
> More details in [the official docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers).

> [!WARNING]
>
> Known issue: getting error `Tool 590_access_sib_biodata_sparql does not have an implementation registered` to fix disable/enable `chat.mcp.enabled` in VSCode `settings.json`, or see this [issue](https://github.com/github/github-mcp-server/issues/177).

## 🛠️ Development

> Requirements: [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle scripts and virtual environments.

### ⚡ Start server

> [!IMPORTANT]
>
> This service requires to have access to a vector database, see the main readme to deploy and index.
>
> ```sh
> docker compose -f compose.dev.yml up vectordb
> ```

Using [SSE](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse) transport at http://0.0.0.0:8888/sse (recommended)

```sh
uv run expasy-mcp
```

Using [STDIO](https://modelcontextprotocol.io/docs/concepts/transports#standard-input%2Foutput-stdio) transport:

```sh
uv run expasy-mcp --stdio
```

> [!NOTE]
>
> Alternative dev environment with the [`mcp`](https://github.com/modelcontextprotocol/python-sdk) package:
>
> ```sh
> uv run mcp dev src/expasy_mcp/server.py
> ```
>
> Or deploy in production:
>
> ```sh
> uv run mcp run src/expasy_mcp/server.py
> ```
>

### 🧹 Format

```bash
uvx ruff format
uvx ruff check --fix
```

### 🔎 Type check

```sh
uv run mypy
```

### 🐳 Start with docker

Ideally deployed alongside a vectordb (see main readme for indexing instructions), here is a `compose.yml` file to deploy the 2:

```yml
services:
  vectordb:
    image: docker.io/qdrant/qdrant:v1.13.4
    restart: unless-stopped
    volumes:
      - ./data/qdrant:/qdrant/storage
    environment:
      - QDRANT__TELEMETRY_DISABLED=true
      - QDRANT_ALLOW_RECOVERY_MODE=true

  mcp-server:
    build: .
    restart: unless-stopped
    depends_on:
      - vectordb
    ports:
      - 8888:8888
    environment:
      - VECTORDB_HOST=vectordb
```
