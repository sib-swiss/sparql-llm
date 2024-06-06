import json
from collections.abc import AsyncGenerator
import os
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI, Stream
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from starlette.middleware.cors import CORSMiddleware

from expasy_chat.embed import QUERIES_COLLECTION, get_embedding_model, get_vectordb

system_prompt = """You are Expasy, an assistant that helps users to query the databases from the Swiss Institute of Bioinformatics, such as UniProt, OMA and Bgee.
When writing the query try to make it as efficient as possible, to avoid timeout due to how large the datasets are.
You can deconstruct complex queries in many smaller queries, but always propose one final query to the user (federated if needed), but be careful to use the right crossref (xref) when using an identifier from an endpoint in another endpoint, and indicate on which endpoint the query should be executed.
"""
# When writing the SPARQL query try to factorize the predicates/objects of a subject as much as possible, so that the user can understand the query and the results.
STARTUP_PROMPT = "Here is a list of questions and SPARQL queries relevant to the user question that can be used on various SPARQL endpoints and might help you answer the user question, use them as inspiration when answering the question from the user:"
INTRO_USER_QUESTION_PROMPT = "The question from the user is:"

client = OpenAI()
vectordb = get_vectordb()
embedding_model = get_embedding_model()

app = FastAPI(
    title="Expasy API",
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
)

templates = Jinja2Templates(
    # directory=pkg_resources.resource_filename("libre_chat", "templates")
    directory="src/expasy_api/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="src/expasy_api/static"),
    name="static",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchResult(BaseModel):
    response: str
    hits_sparql: list[ScoredPoint]
    full_prompt: str


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "mock-gpt-model"
    messages: list[Message]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.1
    stream: Optional[bool] = False
    api_key: Optional[str] = None
    # docs: list[ScoredPoint]


# TODO: make OpenAI compatible endpoint https://towardsdatascience.com/how-to-build-an-openai-compatible-api-87c8edea2f06


async def stream_openai(response: Stream[Any], docs, full_prompt) -> AsyncGenerator[str, None]:
    """Stream the response from OpenAI"""

    first_chunk = {
        "docs": [hit.dict() for hit in docs],
        "full_prompt": full_prompt,
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"

    for chunk in response:
        print(chunk)
        if chunk.choices[0].finish_reason:
            break
        # ChatCompletionChunk(id='chatcmpl-9UxmYAx6E5Y3BXdI7YEVDmbOh9S2X',
        # choices=[Choice(delta=ChoiceDelta(content='', function_call=None, role='assistant', tool_calls=None), finish_reason=None, index=0, logprobs=None)],
        # created=1717166670, model='gpt-4o-2024-05-13', object='chat.completion.chunk', system_fingerprint='fp_319be4768e', usage=None)
        resp_chunk = {
            "id": chunk.id,
            "object": "chat.completion.chunk",
            "created": chunk.created,
            "model": chunk.model,
            "choices": [{"delta": {"content": chunk.choices[0].delta.content}}],
        }
        yield f"data: {json.dumps(resp_chunk)}\n\n"


@app.post("/chat")
async def chat_completions(request: ChatCompletionRequest):
    expasy_key = os.getenv("EXPASY_API_KEY", None)
    if expasy_key and request.api_key != expasy_key:
        return {"error": "Invalid API key"}


    question: str = request.messages[-1].content if request.messages else ""

    query_embeddings = next(iter(embedding_model.embed([question])))
    hits = vectordb.search(
        collection_name=QUERIES_COLLECTION,
        query_vector=query_embeddings,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="sparql"),
                )
            ]
        ),
        limit=10,
    )

    # Either we build a big prompt with the relevant queries retrieved from similarity search engine
    big_prompt = f"{STARTUP_PROMPT}\n\n"

    # Or we provide the example queries as previous messages to the LLM
    example_messages = [{"role": "system", "content": system_prompt}]
    for hit in hits[:3]:
        big_prompt += f"{hit.payload['comment']}\nQuery to run in SPARQL endpoint <{hit.payload['endpoint']}>\n\n{hit.payload['example']}\n\n"

    # Reverse the order of the hits to show the most relevant closest to the user question
    for hit in hits[::-1]:
        example_messages.append({"role": "user", "content": hit.payload["comment"]})
        example_messages.append(
            {
                "role": "assistant",
                "content": f"Query to run in SPARQL endpoint {hit.payload['endpoint']}\n\n```sparql\n{hit.payload['example']}\n```\n",
            }
        )

    big_prompt += f"\n{INTRO_USER_QUESTION_PROMPT}\n{question}"
    example_messages.append({"role": "user", "content": big_prompt})

    # Send the prompt to OpenAI to get a response
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=example_messages,
        # messages=[
        #     {"role": "system", "content": system_prompt},
        #     {"role": "user", "content": full_prompt},
        # ],
        stream=request.stream,
        #   response_format={ "type": "json_object" },
    )
    # TODO: get response as JSON object with SPARQL query separated from explanation?
    # https://github.com/jxnl/instructor or https://github.com/outlines-dev/outlines

    if request.stream:
        return StreamingResponse(stream_openai(response, hits, big_prompt), media_type="application/x-ndjson")

    return {
        "id": response.id,
        "object": "chat.completion",
        "created": response.created,
        "model": response.model,
        "choices": [{"message": Message(role="assistant", content=response.choices[0].message.content)}],
        "docs": hits,
        "full_prompt": big_prompt,
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def chat_ui(request: Request) -> Any:
    """Render the chat UI using jinja2 + HTML"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Expasy query helper",
            "description": "This service helps users to use resources from the Swiss Institute of Bioinformatics, such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.",
            "short_description": "Ask a question about SIB resources.",
            "repository_url": "https://github.com/sib-swiss/expasy-chat",
            "examples": [
                "Which are the genes, expressed in the rat, corresponding to human genes associated with cancer?",
                "What is the gene associated with the protein P12345?",
            ],
            "favicon": "https://www.expasy.org/favicon.ico",
            "expasy_key": os.getenv("EXPASY_API_KEY", None),
        },
    )
