FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
# https://docs.astral.sh/uv/guides/integration/docker

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# COPY pyproject.toml /app/pyproject.toml
# COPY src/expasy-agent/pyproject.toml /app/src/expasy-agent/pyproject.toml
# COPY src/sparql-llm/pyproject.toml /app/src/sparql-llm/pyproject.toml
# RUN uv sync

WORKDIR /app

COPY . /app/

# WORKDIR /app/src/expasy-agent

RUN uv sync --frozen --extra agent

ENV PYTHONUNBUFFERED='1'

# EXPOSE 80
# ENTRYPOINT [ "sleep", "infinity" ]
ENTRYPOINT ["uv", "run", "uvicorn", "src.sparql_llm.agent.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "6", "--log-config", "logging.yml"]
