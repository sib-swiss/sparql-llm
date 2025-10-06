"""API to deploy the Expasy Agent service from LangGraph."""

import asyncio
import json
import logging
import os
import pathlib
import re
from datetime import datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from sparql_llm.agent.config import settings
from sparql_llm.agent.graph import graph
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


# Get the MCP Starlette app and mount routes to it
app = mcp.streamable_http_app()

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
logger.info(f"""⚡️ Streamable HTTP MCP server started on {api_url}/mcp
  💬 Chat UI at {api_url}
  🔎 Using similarity search service on {settings.vectordb_url}""")


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[Message]
    model: str | None = settings.default_llm_model
    max_tokens: int | None = settings.default_max_tokens
    temperature: float | None = settings.default_temperature
    stream: bool | None = False
    validate_output: bool | None = True
    headers: dict[str, str] | None = {}


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
        return obj.model_dump()
    elif hasattr(obj, "dict"):
        return obj.dict()
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return obj


async def stream_response(inputs: dict[str, list], config: RunnableConfig):
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


async def chat_handler(request: Request):
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
        },
        recursion_limit=25,
        callbacks=langfuse_handler,
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
    # print(response)
    return JSONResponse(content=response)


# Add chat routes directly to the MCP app
app.router.add_route("/chat", chat_handler, methods=["POST"])


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


async def feedback_handler(request: Request):
    """Save the user feedback in the logs files."""
    feedback_request = FeedbackRequest(**await request.json())
    filename = (
        f"{settings.logs_folder}/likes.jsonl" if feedback_request.like else f"{settings.logs_folder}/dislikes.jsonl"
    )
    log_msg(filename, feedback_request.messages)
    return JSONResponse(content={"status": "success"})


class LogsRequest(BaseModel):
    api_key: str


async def logs_handler(request: Request):
    """Get the list of user questions from the logs file."""
    logs_request = LogsRequest(**await request.json())
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


async def ui_handler(request: Request) -> HTMLResponse:
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


# Add routes directly to the MCP app
app.router.add_route("/", ui_handler, methods=["GET"])
app.router.add_route("/feedback", feedback_handler, methods=["POST"])
app.router.add_route("/logs", logs_handler, methods=["POST"])


# from ag_ui.core.types import RunAgentInput
# from ag_ui.encoder import EventEncoder
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

# app.router.add_route("/agent", langgraph_agent_endpoint, methods=["POST"])
