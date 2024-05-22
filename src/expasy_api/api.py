import re
from typing import Annotated, Dict, List, Union

from bs4 import BeautifulSoup
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse
from fastembed import TextEmbedding
from pydantic import BaseModel, conint
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
)
from SPARQLWrapper import JSON, SPARQLWrapper
from starlette.middleware.cors import CORSMiddleware
from openai import OpenAI

from expasy_api.vectordb import vectordb, QUERIES_COLLECTION

# Initialize FastEmbed and Qdrant Client
embedding_model = TextEmbedding("BAAI/bge-large-en-v1.5")
embedding_dimensions = 1024

system_prompt = """You are Expasy, an assistant that helps users to query the databases from the Swiss Institute of Bioinformatics, such as UniProt or Bgee.
When writing the SPARQL query try to factorize the predicates/objects of a subject as much as possible, so that the user can understand the query and the results.
"""
STARTUP_PROMPT = "Here are a list of questions and queries that Expasy has learned to answer, use them as base when answering the question from the user:"
INTRO_USER_QUESTION_PROMPT = "The question from the user is:"

# vectordb = QdrantClient(
#     host="qdrant",
#     prefer_grpc=True,
# )
# QUERIES_COLLECTION="expasy-queries"
# print(f"VectorDB loaded with {vectordb.get_collection(QUERIES_COLLECTION).points_count} vectors")
# init_queries_vectordb()

client = OpenAI()

app = FastAPI(
    title="Expasy API",
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchResult(BaseModel):
    response:str

SUMMARY = "Ask a question about SIB resources."
DESCRIPTION = "Returns a response explaining how to use the Swiss Institute of Bioinformatics resources."
ARG_DESCRIPTION = "The question to search for."

@app.get(
    "/ask",
    summary=SUMMARY,
    description=DESCRIPTION,
    response_model=SearchResult,
    tags=["search"],
)
async def ask_get(
    question: Annotated[str, Query(description=ARG_DESCRIPTION)],
) -> SearchResult:
    return await ask_expasy(question)


@app.post(
    "/ask",
    summary=SUMMARY,
    description=DESCRIPTION,
    response_model=SearchResult,
    tags=["search"],
)
async def ask_post(
    question: Annotated[str, Query(description=ARG_DESCRIPTION)],
) -> SearchResult:
    return await ask_expasy(question)


async def ask_expasy(question: str) -> SearchResult:
    query_embeddings = next(iter(embedding_model.embed([question])))

    hits = vectordb.search(
        collection_name=QUERIES_COLLECTION,
        query_vector=query_embeddings,
        limit=50,
    )
    print(len(hits))

    full_prompt = f"{STARTUP_PROMPT}\n\n"
    for hit in hits:
        full_prompt += f"{hit.payload['comment']}\n{hit.payload['query']}\n\n"
        # hit.payload["comment"]

    full_prompt += f"\n{INTRO_USER_QUESTION_PROMPT}\n{question}"

    response = client.chat.completions.create(
        model="gpt-4o",
        #   response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_prompt},
        ]
    )
    # print(response.choices[0].message.content)

    return {"response": response.choices[0].message.content}



@app.get("/", include_in_schema=False)
async def docs_redirect():
    """
    Redirect requests to `/` (where we don't have any content) to `/docs` (which is our Swagger interface).
    """
    return RedirectResponse(url="/docs")