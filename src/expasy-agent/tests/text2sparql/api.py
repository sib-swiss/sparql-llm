"""TEXT2SPARQL API"""

import fastapi

app = fastapi.FastAPI(title="TEXT2SPARQL API")

KNOWN_DATASETS = [
    "https://text2sparql.aksw.org/2025/dbpedia/",
    "https://text2sparql.aksw.org/2025/corporate/"
]

@app.get("/")
async def get_answer(question: str, dataset: str):
    if dataset not in KNOWN_DATASETS:
        raise fastapi.HTTPException(404, "Unknown dataset ...")
    return {
        "dataset": dataset,
        "question": question,
        "query": "... SPARQL here ..."
    }
