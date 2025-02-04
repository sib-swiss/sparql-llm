# 🧑‍💻 Development setup

This page is for if you want to run the package and reusable components in development, and get involved by making a code contribution.

## 📥️ Clone

Clone the repository:

```bash
git clone https://github.com/sib-swiss/sparql-llm
cd sparql-llm
```

## 🐣 Install dependencies

> This repository uses [`hatch`](https://hatch.pypa.io/latest/) to easily handle scripts and virtual environments. Checkout the `pyproject.toml` file for more details on the scripts available. You can also just install dependencies with `pip install ".[chat,test]"` and run the python scripts in `src`

Install [Hatch](https://hatch.pypa.io), this will automatically handle virtual environments and make sure all dependencies are installed when you run a script in the project:

```bash
pipx install hatch
```

## ☑️ Run tests

Make sure the existing tests still work by running the test suite and linting checks. Note that any pull requests to the fairworkflows repository on github will automatically trigger running of the test suite;

```bash
hatch run test
```

To display all logs when debugging:

```bash
hatch run test -s
```

## 🧹 Format code

```bash
hatch run fmt
```

## ♻️ Reset the environment

In case you are facing issues with dependencies not updating properly you can easily reset the virtual environment with:

```bash
hatch env prune
```

Manually trigger installing the dependencies in a local virtual environment:

```bash
hatch -v env create
```

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
