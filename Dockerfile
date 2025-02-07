FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
# https://docs.astral.sh/uv/guides/integration/docker

RUN apt-get update && \
    apt-get install -y git && \
    # gcc build-essential \
    rm -rf /var/lib/apt/lists/*

# COPY pyproject.toml /app/pyproject.toml
# COPY packages/expasy-agent/pyproject.toml /app/packages/expasy-agent/pyproject.toml
# COPY packages/sparql-llm/pyproject.toml /app/packages/sparql-llm/pyproject.toml
# RUN uv sync

COPY . /app/

WORKDIR /app/packages/expasy-agent

RUN uv sync --frozen --extra cpu

ENV PYTHONUNBUFFERED='1'

# ENTRYPOINT [ "sleep", "infinity" ]
ENTRYPOINT ["uv", "run", "uvicorn", "src.expasy_agent.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "6"]
