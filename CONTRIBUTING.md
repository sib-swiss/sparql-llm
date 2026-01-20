# 🧑‍💻 Development

[![PyPI - Version](https://img.shields.io/pypi/v/sparql-llm.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sparql-llm.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

This section is for if you want to run the package and reusable components in development, and get involved by making a code contribution.

> Requirements:
>
> - [x] [`uv`](https://docs.astral.sh/uv/getting-started/installation/), to easily handle scripts and virtual environments
> - [x] docker, to deploy the qdrant vector db and the server

## 📥️ Setup

Clone the repository:

```bash
git clone https://github.com/sib-swiss/sparql-llm
cd sparql-llm
```

Install dev dependencies:

```sh
uv sync --extra agent --group bench
```

Install pre-commit hooks:

```sh
uv run pre-commit install
```

Create a `.env` file at the root of the repository to provide secrets and API keys:

```sh
CHAT_API_KEY=NOT_SO_SECRET_API_KEY_USED_BY_FRONTEND_TO_AVOID_SPAM_FROM_CRAWLERS
LOGS_API_KEY=SECRET_PASSWORD_TO_EASILY_ACCESS_LOGS_THROUGH_THE_API

OPENAI_API_KEY=sk-proj-YYY
OPENROUTER_API_KEY=sk-YYY

LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

## ✅ Run tests

Make sure the existing tests still work by running the test suite and linting checks. Note that any pull requests to the fairworkflows repository on github will automatically trigger running of the test suite;

```bash
uv run pytest
```

To display all logs when debugging:

```bash
uv run pytest -s
```

## 🧹 Format code

```bash
uvx ruff format
uvx ruff check --fix
```

## ⚡️ Run the server

You can run the server with uvicorn:

```sh
uv run --extra agent --env-file .env uvicorn src.sparql_llm.agent.main:app --host 0.0.0.0 --port 8000 --log-config logging.yml --reload
```

Run the MCP server only, with STDIO transport:

```sh
uv run sparql-llm
```

With streamable HTTP transport:

```sh
uv run sparql-llm --http
```

🫆 Start the MCP inspector:

```sh
uv run mcp dev src/sparql_llm/mcp_server.py
```

🔌 Connect a client to the MCP server (cf. `README.md` for more details), the VSCode `mcp.json` should look like below, you will need to change the `cwd` field to provide the path to this repository on your machine:

```json
{
   "servers": {
      "sparql-mcp": {
         "type": "stdio",
         "cwd": "~/dev/sparql-llm",
         "env": {
      	   "SETTINGS_FILEPATH": "sparql-mcp.json"
         },
         "command": "uv",
         "args": [
           "run",
           "sparql-llm"
         ]
      },
      "sparql-mcp-http": {
         "url": "http://localhost:8888/mcp",
         "type": "http"
      },
   }
}
```

> [!NOTE]
>
> Checkout the `README.md` for instructions to run the server in development with docker.

## ♻️ Reset the environment

Upgrade `uv`:

```sh
uv self update
```

Clean `uv` cache:

```sh
uv cache clean
```

## 🏷️ Release process

Get a PyPI API token at [pypi.org/manage/account](https://pypi.org/manage/account).

Run the release script providing the type of version bump: `fix`, `minor`, or `major`

```sh
.github/release.sh fix
```

### 🗞️ Update the MCP Registry entry

Setup [MCP publisher](https://github.com/modelcontextprotocol/registry/blob/main/docs/guides/publishing/publish-server.md):

```sh
brew install mcp-publisher
```

Update the 2 versions fields in the `server.json` file, then update MCP registry entry:

```sh
mcp-publisher login github
mcp-publisher publish
```

> [!NOTE]
>
> [Registry API docs](https://registry.modelcontextprotocol.io/docs)
