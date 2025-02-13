# 🧑‍💻 Development setup

This page is for if you want to run the package and reusable components in development, and get involved by making a code contribution.

## 📥️ Clone

Clone the repository:

```bash
git clone https://github.com/sib-swiss/sparql-llm
cd sparql-llm
```

Requirements: [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle scripts and virtual environments.

## ☑️ Run tests

Make sure the existing tests still work by running the test suite and linting checks. Note that any pull requests to the fairworkflows repository on github will automatically trigger running of the test suite;

```bash
cd packages/sparql-llm
uv run pytest
```

To display all logs when debugging:

```bash
uv run test -s
```

## 🧹 Format code

```bash
uv run ruff format
uv run ruff check --fix
```

## ♻️ Reset the environment

Upgrade `uv`:

```sh
uv self update
```

Clean `uv` cache:

```sh
uv cache clean
```

## 🏷️ New release process

Get a PyPI API token at [pypi.org/manage/account](https://pypi.org/manage/account).

1. Increment the `version` number in the `pyproject.toml` file in the root folder of the repository.

   ```bash
   hatch version fix
   ```

2. Build and publish:

   ```bash
   hatch build
   hatch publish
   ```
