# 🧬 API for Expasy 4

> This repository uses [`hatch`](https://hatch.pypa.io/latest/) to easily handle scripts and virtual environments. Checkout the `pyproject.toml` file for more details on the scripts available.
>
> You can also just install dependencies with `pip install .` and run the python scripts in `src`

## 🚀 Deploy

Add the OpenAI API key to a `.env` file at the root of the repository:

```bash
echo "OPENAI_API_KEY=sk-proj-XXX" > .env
```

Start the API + similarity search engine:

```bash
docker compose up
```

## 🧑‍💻 Development

Start the workspace + similarity search engine:

```bash
docker compose -f docker-compose.dev.yml up
```

Inside the workspace container install the dependencies:

```bash
pip install -e ".[cpu,test]"
```

