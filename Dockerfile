FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim
# https://docs.astral.sh/uv/guides/integration/docker

WORKDIR /app
COPY . /app/

RUN uv sync --frozen --extra agent

ENV PYTHONUNBUFFERED='1'
EXPOSE 80
ENTRYPOINT ["uv", "run", "uvicorn", "src.sparql_llm.agent.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "6", "--log-config", "logging.yml"]
