# 🧑‍💻 Development

[![PyPI - Version](https://img.shields.io/pypi/v/sparql-llm.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sparql-llm.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/sparql-llm/)
[![Tests](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml/badge.svg)](https://github.com/sib-swiss/sparql-llm/actions/workflows/test.yml)

</div>

This section is for if you want to run the package and reusable components in development, and get involved by making a code contribution.

> Requirements: [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle scripts and virtual environments, docker to deploy qdrant and the server

## 📥️ Setup

Clone the repository:

```bash
git clone https://github.com/sib-swiss/sparql-llm
cd sparql-llm
```

Install pre-commit hooks:

```sh
uv run pre-commit install
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

> [!NOTE]
>
> Checkout the `README.md` for instructions to run the server in development with docker.

Test the experimental AG-UI endpoint:

```sh
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "messages": [
    	{"id": "msg_1", "role": "user", "content": "What is the HGNC symbol for the P68871 protein?"}
    ],
    "threadId": "t1",
    "runId": "r1",
    "tools": [],
    "context": [],
    "state": {},
    "forwardedProps" : {}
  }'
```

`"model": "mistralai/mistral-small-latest", "stream": true`

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

1. Increment the `version` number in the `pyproject.toml` file (`fix`, `minor`, or `major`).

   ```bash
   uvx hatch version fix
   ```

2. Build and publish:

   ```bash
   uv build
   uv publish
   ```

3. Create a new tag:

   ```sh
   VERSION=$(uvx hatch version)
   uvx git-cliff -o CHANGELOG.md --tag v$VERSION
   git add CHANGELOG.md src/sparql_llm/__init__.py
   git commit -m "Bump to v$VERSION"
   git tag -a "v$VERSION" -m "Release v$VERSION"
   git push origin "v$VERSION"
   ```

> If `uv publish` is still broken:
>
> ```sh
> uvx hatch build
> uvx hatch publish
> ```
