# Bundle the MCP Apps widgets, git ignored
FROM docker.io/library/node:24-slim AS widgets
WORKDIR /app/widgets
COPY widgets/package.json widgets/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY widgets/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim
# https://docs.astral.sh/uv/guides/integration/docker

WORKDIR /app
COPY . /app/

RUN uv sync --frozen --extra agent

# Outside of `src`, which compose mounts from the host
COPY --from=widgets /app/src/sparql_llm/widgets /app/widgets-dist
ENV WIDGETS_DIR='/app/widgets-dist'

ENV PYTHONUNBUFFERED='1'
EXPOSE 8000
ENTRYPOINT ["uv", "run", "uvicorn", "src.sparql_llm.agent.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "6", "--log-config", "logging.yml"]
