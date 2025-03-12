# Tutorial to build a SPARQL agent

Tutorial slides: [sib-swiss.github.io/sparql-llm](https://sib-swiss.github.io/sparql-llm)

## Deploy the slides locally

On http://localhost:3000/sparql-llm/

```sh
cd slides
npm i
npm run dev
```

## Deploy chat

Create `.env` file with providers API keys:

```sh
OPENAI_API_KEY=sk-proj-YYY
GROQ_API_KEY=gsk_YYY
```

Start vectordb:

```sh
docker compose up -d
```

Index documents:

```sh
uv run index.py
```

On http://localhost:8000

```sh
uv run chainlit run app.py
```
