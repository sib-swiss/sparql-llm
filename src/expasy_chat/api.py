import json
import logging
import os
import re
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security.api_key import APIKey
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI, Stream
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from starlette.middleware.cors import CORSMiddleware

from expasy_chat.embed import ALL_PREFIXES_FILEPATH, DOCS_COLLECTION, get_embedding_model, get_vectordb
from expasy_chat.utils import extract_sparql_queries, queries_pattern

system_prompt = """You are Expasy, an assistant that helps users to navigate the resources and databases from the Swiss Institute of Bioinformatics.
Depending on the user request and provided context, you may provide general information about the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a query: try to make it as efficient as possible to avoid timeout due to how large the datasets are, make sure the query written is valid SPARQL,
always indicate the URL of the endpoint on which the query should be executed in a comment in the codeblocks at the start of the query (no additional text, just the endpoint URL directly as comment, nothing else, and only 1 endpoint).
If answering with a query always derive your answer from the queries provided as examples in the prompt, don't try to create a query from nothing and do not provide a generic query.
If the answer to the question is in the provided context, do not provide a query, just provide the answer, unless explicitly asked.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query.
"""

# If the user is asking about a named entity warn him that they should check if this entity exist with one of the query used to find named entity
# And we provide the this list of queries, and the LLM figure out which query can be used to find the named entity
# https://github.com/biosoda/bioquery/blob/master/biosoda_frontend/src/biosodadata.json#L1491


# and do not put service call to the endpoint the query is run on
# Add a LIMIT 100 to the query and even sub-queries if you are unsure about the size of the result.
# You can deconstruct complex queries in many smaller queries, but always propose one final query to the user (federated if needed), but be careful to use the right crossref (xref) when using an identifier from an endpoint in another endpoint.
# When writing the SPARQL query try to factorize the predicates/objects of a subject as much as possible, so that the user can understand the query and the results.

STARTUP_PROMPT = "Here is a list of reference questions and answers relevant to the user question that will help you answer the user question accurately:"
INTRO_USER_QUESTION_PROMPT = "The question from the user is:"
MAX_TRY_FIX_SPARQL = 10
LLM_MODEL = "gpt-4o"

RETRIEVED_DOCS_COUNT = 20

client = OpenAI()
vectordb = get_vectordb()
embedding_model = get_embedding_model()

app = FastAPI(
    title="Expasy Chat",
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
)

LOGS_FILEPATH = "/logs/user_questions.log"
logging.basicConfig(filename=LOGS_FILEPATH, level=logging.INFO, format="%(asctime)s - %(message)s")

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


@app.post("/chat")
async def chat_completions(request: ChatCompletionRequest):
    expasy_key = os.getenv("EXPASY_API_KEY", None)
    if expasy_key and request.api_key != expasy_key:
        raise ValueError("Invalid API key")

    question: str = request.messages[-1].content if request.messages else ""

    logging.info(f"User question: {question}")

    query_embeddings = next(iter(embedding_model.embed([question])))
    hits = vectordb.search(
        collection_name=DOCS_COLLECTION,
        query_vector=query_embeddings,
        # query_filter=Filter(
        #     must=[
        #         FieldCondition(
        #             key="doc_type",
        #             match=MatchValue(value="sparql"),
        #         )
        #     ]
        # ),
        limit=RETRIEVED_DOCS_COUNT,
    )

    # We build a big prompt with the 3 most relevant queries retrieved from similarity search engine (could be increased)
    big_prompt = f"{STARTUP_PROMPT}\n\n"

    # We also provide the example queries as previous messages to the LLM
    example_messages: list[Message] = [{"role": "system", "content": system_prompt}]
    for hit in hits:
        if hit.payload["doc_type"] == "ontology":
            big_prompt += f"Relevant part of the ontology for {hit.payload['endpoint']}:\n```turtle\n{hit.payload['question']}\n```\n\n"
        else:
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
        model=LLM_MODEL,
        messages=all_messages,
        stream=request.stream,
        #   response_format={ "type": "json_object" },
    )
    # NOTE: to get response as JSON object check https://github.com/jxnl/instructor or https://github.com/outlines-dev/outlines

    if request.stream:
        return StreamingResponse(stream_openai(response, hits, big_prompt), media_type="application/x-ndjson")

    # When streaming is disabled we check if provided SPARQL queries are valid
    chat_resp_md = validate_and_fix_sparql(response.choices[0].message.content, all_messages)

    return {
        "id": response.id,
        "object": "chat.completion",
        "created": response.created,
        "model": response.model,
        "choices": [{"message": Message(role="assistant", content=chat_resp_md)}],
        "docs": hits,
        "full_prompt": big_prompt,
    }
    # NOTE: the response is similar to OpenAI API, but we add the list of hits and the full prompt used to ask the question


def add_missing_prefixes(query: str) -> str:
    """Add missing prefixes to a SPARQL query."""
    with open(ALL_PREFIXES_FILEPATH) as f:
        all_prefixes = json.loads(f.read())
    # Check if the first line is a comment
    lines = query.split("\n")
    comment_line = lines[0].startswith("#") if lines else False
    # Collect prefixes to be added
    prefixes_to_add = []
    for prefix, namespace in all_prefixes.items():
        prefix_str = f"PREFIX {prefix}: <{namespace}>"
        if not re.search(prefix_str, query) and re.search(f"[(| |\u00a0|/]{prefix}:", query):
            prefixes_to_add.append(prefix_str)
            # query = f"{prefix_str}\n{query}"

    if prefixes_to_add:
        prefixes_to_add_str = "\n".join(prefixes_to_add)
        if comment_line:
            lines.insert(1, prefixes_to_add_str)
        else:
            lines.insert(0, prefixes_to_add_str)
        query = "\n".join(lines)
    return query



def validate_and_fix_sparql(md_resp: str, messages: list[Message], try_count: int = 0) -> str:
    """Recursive funtion to validate the SPARQL queries in the chat response and fix them if needed."""

    if try_count >= MAX_TRY_FIX_SPARQL:
        return f"{md_resp}\n\nThe SPARQL query could not be fixed after multiple tries. Please do it yourself!"
    generated_sparqls = extract_sparql_queries(md_resp)

    for gen_query in generated_sparqls:
        try:
            translateQuery(parseQuery(gen_query["query"]))
            # TODO: add more checks, e.g. check composition of the query with VoID?
        except Exception as e:

            if "Unknown namespace prefix" in str(e):
                md_resp = md_resp.replace(gen_query["query"], add_missing_prefixes(gen_query["query"]))
            else:
                # Ask the LLM to try to fix it
                print(f"Error in SPARQL query try #{try_count}: {e}\n{gen_query['query']}")
                try_count += 1
                fix_prompt = f"""There is an error `{e}` in the generated SPARQL query:
    {gen_query["query"]}

    Which is part of this answer:
    {md_resp}

    Fix the SPARQL query in a way that it is a fully valid query, and send the answer again with the fixed query.
    """
                messages.append({"role": "assistant", "content": fix_prompt})
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    stream=False,
                )
                md_resp = response.choices[0].message.content
            # Check again the fixed query
            return validate_and_fix_sparql(md_resp, messages, try_count)
    return md_resp


class FeedbackRequest(BaseModel):
    like: bool
    messages: list[Message]

@app.post("/feedback", response_model=list[str])
def post_like(request: FeedbackRequest):
    """Save the user feedback in the logs files."""
    timestamp = datetime.now().isoformat()
    file_name = "/logs/likes.jsonl" if request.like else "/logs/dislikes.jsonl"
    feedback_data = {
        "timestamp": timestamp,
        "messages": [message.model_dump() for message in request.messages]
    }
    with open(file_name, "a") as f:
        f.write(json.dumps(feedback_data) + "\n")
    return request.messages

class LogsRequest(BaseModel):
    api_key: str

@app.post("/logs", response_model=list[str])
def get_user_logs(request: LogsRequest):
    """Get the list of user questions from the logs file."""
    logs_key = os.getenv("LOGS_API_KEY", None)
    if logs_key and request.api_key != logs_key:
        raise ValueError("Invalid API key")
    questions = set()
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - User question: (.+)")
    with open(LOGS_FILEPATH) as file:
        for line in file:
            match = pattern.search(line)
            if match:
                # date_time = match.group(1)
                question = match.group(2)
                # questions.append({"date": date_time, "question": question})
                questions.add(question)

    return list(questions)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def chat_ui(request: Request) -> Any:
    """Render the chat UI using jinja2 + HTML"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Ask Expasy",
            "description": """Assistant to navigate resources from the Swiss Institute of Bioinformatics. Particularly knowledgeable about UniProt, OMA, Bgee, RheaDB, and SwissLipids. But still learning.

Contact kru@sib.swiss if you have any feedback or suggestions.
""",
            "short_description": "Ask about SIB resources.",
            "repository_url": "https://github.com/sib-swiss/expasy-chat",
            "examples": [
                "Which resources are available at the SIB?",
                "How can I get the HGNC symbol for the protein P68871?",
                "What are the rat orthologs of the human TP53?",
                "Where is expressed the gene ACE2 in human?",
                # "Say hi",
                # "Which are the genes, expressed in the rat, corresponding to human genes associated with cancer?",
                # "What is the gene associated with the protein P68871?",
            ],
            "favicon": "https://www.expasy.org/favicon.ico",
            "expasy_key": os.getenv("EXPASY_API_KEY", None),
        },
    )
