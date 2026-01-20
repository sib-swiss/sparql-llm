"""API to deploy the Expasy Agent service from LangGraph."""

import asyncio
import contextlib
import json
import logging
import os
import pathlib
import re
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel

from sparql_llm.agent.graph import graph
from sparql_llm.config import settings
from sparql_llm.mcp_server import mcp
from sparql_llm.utils import logger

if settings.sentry_url:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_url,
        # Add data like request headers and IP for users, see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
        # Set traces_sample_rate to 1.0 to capture 100% of transactions for tracing.
        traces_sample_rate=0.0,
    )


# Initialize Langfuse logs tracing CallbackHandler for Langchain https://langfuse.com/docs/integrations/langchain/example-python-langgraph
langfuse_handler = [CallbackHandler()] if os.getenv("LANGFUSE_SECRET_KEY") else []


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan that initializes the MCP session manager."""
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title=settings.app_name,
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/mcp", mcp.streamable_http_app(), name="mcp")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create logs file if it doesn't exist
question_logger = logging.getLogger("question_logger")
question_logger.setLevel(logging.INFO)
try:
    if not os.path.exists(settings.logs_filepath):
        pathlib.Path(settings.logs_filepath).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(settings.logs_filepath).touch()
    file_handler = logging.FileHandler(settings.logs_filepath)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    question_logger.addHandler(file_handler)
except Exception:
    logger.warning(f"⚠️ Logs filepath {settings.logs_filepath} not writable.")

uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.WARNING)

api_url = "http://localhost:8000"
logger.info(f"""💬 Chat UI at {api_url}
  ⚡️ Streamable HTTP MCP server started on {api_url}/mcp
  🔎 Using similarity search service on {settings.vectordb_url}
""")


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[Message]
    model: str = settings.default_llm_model
    max_tokens: int = settings.default_max_tokens
    temperature: float = settings.default_temperature
    stream: bool = False
    validate_output: bool = True
    enable_sparql_execution: bool = True
    headers: dict[str, str] = {}


def convert_chunk_to_dict(obj: Any) -> Any:
    """Recursively convert a langgraph chunk object to a dict.

    Required because LangGraph objects are not serializable by default.
    And they use a mix of tuples, dataclasses (State, Configuration) and pydantic BaseModel (BaseMessage).
    """
    # {'retrieve': {'retrieved_docs': [Document(metadata={'endpoint_url':
    # When sending a msg LangGraph sends a tuple with the message and the metadata
    if isinstance(obj, tuple) and len(obj) == 2:
        # Message and metadata
        return [convert_chunk_to_dict(obj[0]), convert_chunk_to_dict(obj[1])]
    elif isinstance(obj, list):
        return [convert_chunk_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_chunk_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore
    elif hasattr(obj, "dict"):
        return obj.dict()  # type: ignore
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    # elif hasattr(obj, "__dict__") and not isinstance(obj, type):
    #     # Convert dataclass or other objects to dict, but skip type objects
    #     return {k: convert_chunk_to_dict(v) for k, v in obj.__dict__.items()}
    else:
        return obj


async def stream_response(inputs: Any, config: RunnableConfig) -> AsyncGenerator[str, Any]:
    """Stream the response from the assistant."""
    async for event, chunk in graph.astream(inputs, stream_mode=["messages", "updates"], config=config):
        chunk_dict = convert_chunk_to_dict(
            {
                "event": event,
                "data": chunk,
            }
        )
        # print(chunk_dict)
        # TODO: log_msg(logs_folder + "/all.jsonl", full_messages) when complete
        yield f"data: {json.dumps(chunk_dict)}\n\n"
        await asyncio.sleep(0)
    yield "data: [DONE]"


# FastAPI does not support Union in response model (even if it says otherwise in docs)
# so we need to disable response_model for this endpoint
@app.post("/chat", response_model=None)
async def chat(request: Request) -> StreamingResponse | JSONResponse:
    """Chat with the assistant main endpoint."""
    auth_header = request.headers.get("Authorization", "")
    if settings.chat_api_key and (not auth_header or not auth_header.startswith("Bearer ")):
        raise ValueError("Missing or invalid Authorization header")
    if settings.chat_api_key and auth_header.split(" ")[1] != settings.chat_api_key:
        raise ValueError("Invalid API key")

    chat_request = ChatCompletionRequest(**await request.json())
    # request.messages = [msg for msg in request.messages if msg.role != "system"]
    # request.messages = [Message(role="system", content=settings.system_prompt), *request.messages]

    question: str = chat_request.messages[-1].content if chat_request.messages else ""
    question_logger.info(f"User question: {question}")
    if not question:
        raise ValueError("No question provided")

    # print(request.model)
    config = RunnableConfig(
        configurable={
            "model": chat_request.model,
            "validate_output": chat_request.validate_output,
            "enable_sparql_execution": chat_request.enable_sparql_execution,
        },
        recursion_limit=25,
        callbacks=langfuse_handler,  # type: ignore
    )
    inputs: Any = {
        "messages": [(msg.role, msg.content) for msg in chat_request.messages],
    }

    # request.stream = False
    if chat_request.stream:
        return StreamingResponse(
            stream_response(inputs, config),
            media_type="text/event-stream",
            # media_type="application/x-ndjson"
        )

    response = await graph.ainvoke(inputs, config=config)
    # Convert LangChain message objects to dicts for JSON serialization
    response_dict = convert_chunk_to_dict(response)
    return JSONResponse(content=response_dict)


class LogMessage(Message):
    """Message model for logging purposes."""

    steps: list[Any] | None = None


class FeedbackRequest(BaseModel):
    like: bool
    messages: list[LogMessage]


def log_msg(filename: str, messages: list[LogMessage]) -> None:
    """Log a messages thread to a log file."""
    timestamp = datetime.now().isoformat()
    feedback_data = {
        "timestamp": timestamp,
        "messages": [message.model_dump() for message in messages],
    }
    with open(filename, "a") as f:
        f.write(json.dumps(feedback_data) + "\n")


@app.post("/feedback")
async def post_feedback(feedback_request: FeedbackRequest) -> JSONResponse:
    """Save a user feedback in the logs files."""
    filename = (
        f"{settings.logs_folder}/likes.jsonl" if feedback_request.like else f"{settings.logs_folder}/dislikes.jsonl"
    )
    log_msg(filename, feedback_request.messages)
    return JSONResponse(content={"status": "success"})


class LogsRequest(BaseModel):
    api_key: str


@app.post("/logs", response_model=list[str])
async def get_user_logs(logs_request: LogsRequest) -> JSONResponse:
    """Get the list of user questions from the logs file."""
    if settings.logs_api_key and logs_request.api_key != settings.logs_api_key:
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
    return JSONResponse(content=list(questions))


# Serve website built using vitejs
templates = Jinja2Templates(directory="src/sparql_llm/agent/webapp")
app.mount(
    "/assets",
    StaticFiles(directory="src/sparql_llm/agent/webapp/assets"),
    name="static",
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def chat_ui(request: Request) -> HTMLResponse:
    """Render the chat UI using jinja2 + HTML."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "api_key": settings.chat_api_key,
            "chat_endpoint": "/chat",
            "feedback_endpoint": "/feedback",
            "examples": ",".join(settings.example_questions),
        },
    )


# NOTE: experimental AG-UI endpoint
# from ag_ui.core.types import RunAgentInput
# from ag_ui.encoder import EventEncoder
# @app.post("/agent", response_model=list[str])
# async def langgraph_agent_endpoint(request: Request):
#     """Handle LangGraph agent requests with SSE streaming."""
#     # Parse the request body
#     input_data = RunAgentInput(**await request.json())
#     # Get the accept header from the request
#     accept_header = request.headers.get("accept")
#     # Create an event encoder to properly format SSE events
#     encoder = EventEncoder(accept=accept_header)
#     async def event_generator():
#         async for event in graph.run(input_data):
#             yield encoder.encode(event)
#     return StreamingResponse(
#         event_generator(),
#         media_type=encoder.get_content_type()
#     )

# Test it:
# curl -X POST http://localhost:8000/agent -H "Content-Type: application/json" -H "Accept: text/event-stream" -d '{
#  "messages": [
#  	 {"id": "msg_1", "role": "user", "content": "What is the HGNC symbol for the P68871 protein?"}
#  ],
#  "threadId": "t1", "runId": "r1", "tools": [], "context": [], "state": {}, "forwardedProps" : {}
# }'
