import json
from collections.abc import AsyncGenerator
import os
from typing import Any, Optional
import logging
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI, Stream
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from starlette.middleware.cors import CORSMiddleware

from expasy_chat.embed import QUERIES_COLLECTION, get_embedding_model, get_vectordb

system_prompt = """You are Expasy, an assistant that helps users to navigate the resources and databases from the Swiss Institute of Bioinformatics.
Depending on the user request you may provide general information about the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a query try to make it as efficient as possible, to avoid timeout due to how large the datasets are. Add a LIMIT 100 to the query and even sub-queries if you are unsure about the size of the result.
If answering with a query always indicate the URL of the endpoint on which the query should be executed in a comment in the codeblocks at the start of the query. No additional text, just the endpoint URL directly as comment, and do not put service call to the endpoint the query is run on.
If answering with a query always use the queries provided as examples in the prompt, don't try to create a query from nothing and do not provide a super generic query.
"""
# You can deconstruct complex queries in many smaller queries, but always propose one final query to the user (federated if needed), but be careful to use the right crossref (xref) when using an identifier from an endpoint in another endpoint.
# When writing the SPARQL query try to factorize the predicates/objects of a subject as much as possible, so that the user can understand the query and the results.
STARTUP_PROMPT = "Here is a list of reference questions and answers relevant to the user question that will help you answer the user question accurately:"
INTRO_USER_QUESTION_PROMPT = "The question from the user is:"

client = OpenAI()
vectordb = get_vectordb()
embedding_model = get_embedding_model()

app = FastAPI(
    title="Expasy Chat",
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
)

logging.basicConfig(filename="/logs/user_questions.log", level=logging.INFO, format="%(asctime)s - %(message)s")

templates = Jinja2Templates(directory="src/expasy_chat/templates")
app.mount(
    "/static",
    StaticFiles(directory="src/expasy_chat/static"),
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
    model: Optional[str] = "expasy"
    messages: list[Message]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.1
    stream: Optional[bool] = False
    api_key: Optional[str] = None


async def stream_openai(response: Stream[Any], docs, full_prompt) -> AsyncGenerator[str, None]:
    """Stream the response from OpenAI"""

    first_chunk = {
        "docs": [hit.dict() for hit in docs],
        "full_prompt": full_prompt,
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"

    for chunk in response:
        if chunk.choices[0].finish_reason:
            break
        # print(chunk)
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

DOCS_COUNT = 10

@app.post("/chat")
async def chat_completions(request: ChatCompletionRequest):
    expasy_key = os.getenv("EXPASY_API_KEY", None)
    if expasy_key and request.api_key != expasy_key:
        raise ValueError("Invalid API key")

    question: str = request.messages[-1].content if request.messages else ""

    logging.info(f"User question: {question}")

    query_embeddings = next(iter(embedding_model.embed([question])))
    hits = vectordb.search(
        collection_name=QUERIES_COLLECTION,
        query_vector=query_embeddings,
        # query_filter=Filter(
        #     must=[
        #         FieldCondition(
        #             key="doc_type",
        #             match=MatchValue(value="sparql"),
        #         )
        #     ]
        # ),
        limit=DOCS_COUNT,
    )

    # We build a big prompt with the 3 most relevant queries retrieved from similarity search engine (could be increased)
    big_prompt = f"{STARTUP_PROMPT}\n\n"

    # We also provide the example queries as previous messages to the LLM
    example_messages: list[Message] = [{"role": "system", "content": system_prompt}]
    for hit in hits:
        big_prompt += f"{hit.payload['question']}\nQuery to run in SPARQL endpoint {hit.payload['endpoint']}\n\n{hit.payload['answer']}\n\n"

    # Reverse the order of the hits to show the most relevant closest to the user question
    # NOTE: this breaks the memory
    # for hit in hits[::-1]:
    #     example_messages.append({"role": "user", "content": hit.payload["comment"]})
    #     example_messages.append(
    #         {
    #             "role": "assistant",
    #             "content": f"Query to run in SPARQL endpoint {hit.payload['endpoint']}\n\n```sparql\n{hit.payload['example']}\n```\n",
    #         }
    #     )

    big_prompt += f"\n{INTRO_USER_QUESTION_PROMPT}\n{question}"

    request.messages[-1].content = big_prompt
    all_messages = example_messages + request.messages
    # all_messages.append({"role": "user", "content": big_prompt})

    # print(all_messages)

    # Send the prompt to OpenAI to get a response
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=all_messages,
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

    # NOTE: the response is similar to OpenAI API, but we add the list of hits and the full prompt used to ask the question
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
            "title": "Ask Expasy",
            "description": "Assistant to navigate resources from the Swiss Institute of Bioinformatics.",
            "short_description": "Ask a question about SIB resources.",
            "repository_url": "https://github.com/sib-swiss/expasy-chat",
            "examples": [
                "Which resources are available at the SIB?",
                "How can I get the HGNC symbol for the protein P68871?",
                # "Which are the genes, expressed in the rat, corresponding to human genes associated with cancer?",
                # "What is the gene associated with the protein P68871?",
            ],
            "favicon": "https://www.expasy.org/favicon.ico",
            "expasy_key": os.getenv("EXPASY_API_KEY", None),
        },
    )
