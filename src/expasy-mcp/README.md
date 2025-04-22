# 🧬 BioData MCP

A Model Context Protocol (MCP) server to access biodata resources at the SIB, such as SPARQL endpoints and APIs.

## 🪄 Available tools

- 📝 Help users to **write SPARQL queries** to access SIB biodata resources
  - Required arguments:
    - `question` (string): the user's question

- 📡  **Execute a SPARQL query** against a SPARQL endpoint
  - Required arguments:
    - `query` (string): a valid SPARQL query string
    - `endpoint` (string): the SPARQL endpoint URL to execute the query against

- ✅ **Validate a SPARQL query** destinated to a SPARQL endpoint using the VoID description of the endpoint when available
  - Required arguments:
    - `query` (string): a SPARQL query string
    - `endpoint` (string): the SPARQL endpoint URL to which the query is designated

> [!WARNING]
>
> Experimental.

## 🔌 Connect client

Follow the instructions of your client, and use the `/sse` URL of your deployed server (e.g. http://0.0.0.0:8888/sse)

### 🐙 GitHub Copilot

Open side panel chat (cmd+shift+i) > bottom right set the mode to `Agent` > Click the wrench and screwdriver button ("Select Tools...") > `Add MCP server...` > provide the URL to the MCP server, by default http://0.0.0.0:8888/sse

In VSCode you need to enable the following:

```sh
		"chat.agent.enabled": true,
    "chat.mcp.enabled": true,
    "mcp": {
        "servers": {
            "expasy-mcp": {
                "type": "sse",
                "url": "http://0.0.0.0:8888/sse"
            }
        }
    }
```

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

