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
MISTRAL_API_KEY=YYY
GROQ_API_KEY=YYY
OPENAI_API_KEY=sk-proj-YYY
```

Start on http://localhost:8000

```sh
uv run chainlit run app.py
```

Reset vectordb:

```sh
rm -rf data/vectordb
```

> [!NOTE]
>
> Or just run the `main` function:
>
> ```sh
> uv run --env-file .env app.py
> ```

## Tutorial history

- 1st version (05-2025)
  - Commit: https://github.com/sib-swiss/sparql-llm/tree/1bbb129c239e41f8fd33f7bba7444173e1b5e380
  - Slides: https://docs.google.com/presentation/d/17gdGSkxFe-5WLRlgB0RrjQ_GHUf5Osej/edit
