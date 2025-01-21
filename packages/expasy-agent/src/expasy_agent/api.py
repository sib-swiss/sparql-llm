"""API to deploy the Expasy Agent service from LangGraph."""

import asyncio
import json
import logging
import os
import pathlib
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from expasy_agent.config import settings
from expasy_agent.graph import graph

# llm_model = "gpt-4o"
# llm_model = "azure_ai/mistral-large"
# llm_model: str = "gpt-4o-mini"

# Models from glhf:
# llm_model: str = "hf:meta-llama/Meta-Llama-3.1-8B-Instruct"
# llm_model: str = "hf:mistralai/Mixtral-8x22B-Instruct-v0.1"
# llm_model: str = "hf:mistralai/Mistral-7B-Instruct-v0.3"
# Not working in glhf
# llm_model: str = "hf:meta-lama/Meta-Llama-3.1-405B-Instruct"

app = FastAPI(
    title="Expasy GPT",
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

# Create logs file if it doesn't exist
try:
    if not os.path.exists(settings.logs_filepath):
        pathlib.Path(settings.logs_filepath).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(settings.logs_filepath).touch()
    logging.basicConfig(filename=settings.logs_filepath, level=logging.INFO, format="%(asctime)s - %(message)s")
except Exception:
    logging.warning(f"⚠️ Logs filepath {settings.logs_filepath} not writable.")

class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[Message]
    model: Optional[str] = "gpt-4o"
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.0
    stream: Optional[bool] = False
    validate_output: Optional[bool] = True
    headers: Optional[dict[str, str]] = {}


def convert_chunk_to_dict(obj: Any) -> Any:
    """Recursively convert a langgraph chunk object to a dict.

    Required because LangGraph objects are not serializable by default.
    And they use a mix of tuples, dataclasses (BaseMessage) and pydantic BaseModel (BaseMessage).
    """
    # {'retrieve': {'retrieved_docs': [Document(metadata={'endpoint_url':
    # When sending a msg LangGraph sends a tuple with the message and the metadata
    if isinstance(obj, tuple):
        # Message and metadata
        return [convert_chunk_to_dict(obj[0]), convert_chunk_to_dict(obj[1])]
    elif isinstance(obj, list):
        return [convert_chunk_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_chunk_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "dict"):
        return obj.dict()
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return obj


async def stream_response(inputs: dict[str, list]):
    """Stream the response from the assistant."""
    async for event, chunk in graph.astream(inputs, stream_mode=["messages", "updates"]):
        # print(event)
        chunk_dict = convert_chunk_to_dict({
            "event": event,
            "data": chunk,
        })
        yield f"{json.dumps(chunk_dict)}\n"
        # yield stream_dict(chunk)
        await asyncio.sleep(0)

    # TODO: Extract potential entities from the user question (experimental)
    # entities_list = extract_entities(question)
    # for entity in entities_list:
    #     prompt += f'\n\nEntities found in the user question for "{" ".join(entity["term"])}":\n\n'
    #     for match in entity["matchs"]:
    #         prompt += f"- {match.payload['label']} with IRI <{match.payload['uri']}> in endpoint {match.payload['endpoint_url']}\n\n"
    # if len(entities_list) == 0:
    #     prompt += "\nNo entities found in the user question that matches entities in the endpoints. "
    # prompt += "\nIf the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"



def stream_dict(d: dict) -> str:
    """Stream a dictionary as a JSON string."""
    return f"data: {json.dumps(d)}\n\n"


# @app.post("/chat/completions")
@app.post("/chat")
async def chat(request: ChatCompletionRequest):
    """Chat with the assistant main endpoint."""
    auth_header = request.headers.get("Authorization")
    if settings.expasy_api_key and (not auth_header or not auth_header.startswith("Bearer ")):
        raise ValueError("Missing or invalid Authorization header")
    if settings.expasy_api_key and auth_header.split(" ")[1] != settings.expasy_api_key:
        raise ValueError("Invalid API key")

    # request = ChatCompletionRequest(**await request.json())
    # request.messages = [msg for msg in request.messages if msg.role != "system"]
    # request.messages = [Message(role="system", content=settings.system_prompt), *request.messages]

    question: str = request.messages[-1].content if request.messages else ""
    logging.info(f"User question: {question}")
    if not question:
        raise ValueError("No question provided")

    inputs = {
        "messages": [(msg.role, msg.content) for msg in request.messages],
    }

    # request.stream = False
    if request.stream:
        return StreamingResponse(
            stream_response(inputs),
            media_type="text/event-stream",
            # media_type="application/x-ndjson"
        )

    response = await graph.ainvoke(inputs)
    # print(response)
    return response


# TODO: improve and integrate in retrieval step + use langchain retriever
# def extract_entities(sentence: str) -> list[dict[str, str]]:
#     score_threshold = 0.8
#     sentence_splitted = re.findall(r"\b\w+\b", sentence)
#     window_size = len(sentence_splitted)
#     entities_list = []
#     while window_size > 0 and window_size <= len(sentence_splitted):
#         window_start = 0
#         window_end = window_start + window_size
#         while window_end <= len(sentence_splitted):
#             term = sentence_splitted[window_start:window_end]
#             print("term", term)
#             term_embeddings = next(iter(embedding_model.embed([" ".join(term)])))
#             query_hits = vectordb.search(
#                 collection_name=settings.entities_collection_name,
#                 query_vector=term_embeddings,
#                 limit=10,
#             )
#             matchs = []
#             for query_hit in query_hits:
#                 if query_hit.score > score_threshold:
#                     matchs.append(query_hit)
#             if len(matchs) > 0:
#                 entities_list.append(
#                     {
#                         "matchs": matchs,
#                         "term": term,
#                         "start_index": window_start,
#                         "end_index": window_end,
#                     }
#                 )
#             # term_search = reduce(lambda x, y: "{} {}".format(x, y), sentence_splitted[window_start:window_end])
#             # resultSearch = index.search(term_search)
#             # if resultSearch is not None and len(resultSearch) > 0:
#             #     selected_hit = resultSearch[0]
#             #     if selected_hit['score'] > MAX_SCORE_PARSER_TRIPLES:
#             #         selected_hit = None
#             #     if selected_hit is not None and selected_hit not in matchs:
#             #         matchs.append(selected_hit)
#             window_start += 1
#             window_end = window_start + window_size
#         window_size -= 1
#     return entities_list


class FeedbackRequest(BaseModel):
    like: bool
    messages: list[Message]


@app.post("/feedback", response_model=list[str])
def post_like(request: FeedbackRequest):
    """Save the user feedback in the logs files."""
    timestamp = datetime.now().isoformat()
    file_name = "/logs/likes.jsonl" if request.like else "/logs/dislikes.jsonl"
    feedback_data = {"timestamp": timestamp, "messages": [message.model_dump() for message in request.messages]}
    with open(file_name, "a") as f:
        f.write(json.dumps(feedback_data) + "\n")
    return request.messages


class LogsRequest(BaseModel):
    api_key: str


@app.post("/logs", response_model=list[str])
def get_user_logs(request: LogsRequest):
    """Get the list of user questions from the logs file."""
    if settings.logs_api_key and request.api_key != settings.logs_api_key:
        raise ValueError("Invalid API key")
    questions = set()
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - User question: (.+)")
    with open(settings.logs_filepath) as file:
        for line in file:
            match = pattern.search(line)
            if match:
                # date_time = match.group(1)
                question = match.group(2)
                # questions.append({"date": date_time, "question": question})
                questions.add(question)

    return list(questions)

# Serve website built from SolidJS
templates = Jinja2Templates(directory="src/expasy_agent/webapp")
app.mount(
    "/assets",
    StaticFiles(directory="src/expasy_agent/webapp/assets"),
    name="static",
)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def chat_ui(request: Request) -> Any:
    """Render the chat UI using jinja2 + HTML."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "api_key": settings.expasy_api_key,
            "chat_endpoint": "https://chat.expasy.org/chat",
            "feedback_endpoint": "https://chat.expasy.org/feedback",
            "examples": ",".join([
                "Which resources are available at the SIB?",
                "How can I get the HGNC symbol for the protein P68871?",
                "What are the rat orthologs of the human TP53?",
                "Where is expressed the gene ACE2 in human?",
                "Anatomical entities where the INS zebrafish gene is expressed and its gene GO annotations",
                "List the genes in primates orthologous to genes expressed in the fruit fly eye",
                # "Say hi",
                # "Which are the genes, expressed in the rat, corresponding to human genes associated with cancer?",
                # "What is the gene associated with the protein P68871?",
            ]),
#             "title": "Ask Expasy",
#             "llm_model": llm_model,
#             "description": """Assistant to navigate resources from the Swiss Institute of Bioinformatics. Particularly knowledgeable about UniProt, OMA, Bgee, RheaDB, and SwissLipids. But still learning.

# Contact kru@sib.swiss if you have any feedback or suggestions. Questions asked here are stored for research purposes, see the [SIB privacy policy](https://www.sib.swiss/privacy-policy) for more information.
# """,
#             "short_description": "Ask about SIB resources.",
#             "repository_url": "https://github.com/sib-swiss/sparql-llm",
#             "favicon": "https://www.expasy.org/favicon.ico",
        },
    )
