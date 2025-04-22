FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
# https://docs.astral.sh/uv/guides/integration/docker

COPY . /app/
WORKDIR /app

RUN uv sync

ENV PYTHONUNBUFFERED='1'
EXPOSE 8888
ENTRYPOINT ["uv", "run", "src/expasy_mcp/server.py"]
