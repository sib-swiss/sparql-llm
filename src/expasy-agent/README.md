# Expasy Agent - a SPARQL assistant

## Run in dev

> [!TIP]
>
> We recommend to use the docker compose setup described in the `README.md` file at the root of the repository.

1. Start the vectordb using the docker compose file at the root of the repository:

   ```sh
   docker compose -f compose.dev.yml up vectordb
   ```

2. Run custom LangGraph API on http://localhost:8000/docs/

   ```sh
   cd src/expasy-agent
   uv run --extra cpu uvicorn src.expasy_agent.main:app --reload
   ```

   Alternatively you can use the closed source LanGraph Platform On http://127.0.0.1:2024:

   ```sh
   cd src/expasy-agent
   uv run --extra cpu langgraph dev
   ```

### Test

```sh
uv run --extra cpu --env-file .env pytest
```

### Build for prod

```sh
uv run langgraph build -t langgraph-expasy-agent
uv run langgraph up
docker compose up
```
