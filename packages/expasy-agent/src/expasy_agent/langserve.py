import json
import re
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langserve import add_routes
from pydantic import BaseModel
from sparql_llm.config import settings
from starlette.middleware.cors import CORSMiddleware

from expasy_agent import graph

app = FastAPI(
    title="Expasy Chat",
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
)

# JS for langserve https://js.langchain.com/v0.1/docs/ecosystem/langserve/
# logging.basicConfig(filename=settings.logs_filepath, level=logging.INFO, format="%(asctime)s - %(message)s")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_routes(
    app,
    graph,
    path="/langgraph",
    config_keys=["configurable"],
    # playground_type="chat",
)

class Message(BaseModel):
    role: str
    content: str

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

# templates = Jinja2Templates(directory="src/sparql_llm/templates")
# app.mount(
#     "/static",
#     StaticFiles(directory="src/sparql_llm/static"),
#     name="static",
# )

# templates = Jinja2Templates(directory="src/sparql_llm/webapp")
# app.mount(
#     "/assets",
#     StaticFiles(directory="src/sparql_llm/webapp/assets"),
#     name="static",
# )

# # app.mount(
# #     "/",
# #     StaticFiles(
# #         directory=pkg_resources.resource_filename("sparql_llm", "webapp"), html=True
# #     ),
# #     name="static",
# # )

# @app.get("/", response_class=HTMLResponse, include_in_schema=False)
# def chat_ui(request: Request) -> Any:
#     """Render the chat UI using jinja2 + HTML."""
#     return templates.TemplateResponse(
#         "index.html",
#         {
#             "request": request,
#             "expasy_key": settings.expasy_api_key,
#             "api_url": "https://chat.expasy.org/",
#             "examples": ",".join([
#                 "Which resources are available at the SIB?",
#                 "How can I get the HGNC symbol for the protein P68871?",
#                 "What are the rat orthologs of the human TP53?",
#                 "Where is expressed the gene ACE2 in human?",
#                 "Anatomical entities where the INS zebrafish gene is expressed and its gene GO annotations",
#                 "List the genes in primates orthologous to genes expressed in the fruit fly eye",
#                 # "Say hi",
#                 # "Which are the genes, expressed in the rat, corresponding to human genes associated with cancer?",
#                 # "What is the gene associated with the protein P68871?",
#             ]),
# #             "title": "Ask Expasy",
# #             "llm_model": llm_model,
# #             "description": """Assistant to navigate resources from the Swiss Institute of Bioinformatics. Particularly knowledgeable about UniProt, OMA, Bgee, RheaDB, and SwissLipids. But still learning.

# # Contact kru@sib.swiss if you have any feedback or suggestions. Questions asked here are stored for research purposes, see the [SIB privacy policy](https://www.sib.swiss/privacy-policy) for more information.
# # """,
# #             "short_description": "Ask about SIB resources.",
# #             "repository_url": "https://github.com/sib-swiss/sparql-llm",
# #             "favicon": "https://www.expasy.org/favicon.ico",
#         },
#     )
