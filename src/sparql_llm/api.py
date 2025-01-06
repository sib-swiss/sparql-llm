import json
import logging
import re
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from litellm import completion
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from starlette.middleware.cors import CORSMiddleware

from sparql_llm.config import get_prefixes_dict, settings
from sparql_llm.index import get_embedding_model, get_vectordb
from sparql_llm.utils import get_prefix_converter
from sparql_llm.validate_sparql import add_missing_prefixes, extract_sparql_queries, validate_sparql_with_void

# If the user is asking about a named entity warn him that they should check if this entity exist with one of the query used to find named entity
# And we provide the this list of queries, and the LLM figure out which query can be used to find the named entity
# https://github.com/biosoda/bioquery/blob/master/biosoda_frontend/src/biosodadata.json#L1491

# and do not put service call to the endpoint the query is run on
# Add a LIMIT 100 to the query and even sub-queries if you are unsure about the size of the result.
# You can deconstruct complex queries in many smaller queries, but always propose one final query to the user (federated if needed), but be careful to use the right crossref (xref) when using an identifier from an endpoint in another endpoint.
# When writing the SPARQL query try to factorize the predicates/objects of a subject as much as possible, so that the user can understand the query and the results.

STARTUP_PROMPT = "Here is a list of reference questions and query answers relevant to the user question that will help you answer the user question accurately:"
INTRO_USER_QUESTION_PROMPT = "The question from the user is:"

# llm_model = "gpt-4o"
llm_model = "azure_ai/mistral-large"
# llm_model: str = "gpt-4o-mini"

# Models from glhf:
# llm_model: str = "hf:meta-llama/Meta-Llama-3.1-8B-Instruct"
# llm_model: str = "hf:mistralai/Mixtral-8x22B-Instruct-v0.1"
# llm_model: str = "hf:mistralai/Mistral-7B-Instruct-v0.3"
# Not working in glhf
# llm_model: str = "hf:meta-lama/Meta-Llama-3.1-405B-Instruct"

vectordb = get_vectordb()
embedding_model = get_embedding_model()

app = FastAPI(
    title="Expasy Chat",
    description="""This service helps users to use resources from the Swiss Institute of Bioinformatics,
such as SPARQL endpoints, to get information about proteins, genes, and other biological entities.""",
)

logging.basicConfig(filename=settings.logs_filepath, level=logging.INFO, format="%(asctime)s - %(message)s")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefixes_map = get_prefixes_dict()
prefix_converter = get_prefix_converter(prefixes_map)


class SearchResult(BaseModel):
    response: str
    hits_sparql: list[ScoredPoint]
    full_prompt: str


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[Message]
    model: Optional[str] = llm_model
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.0
    stream: Optional[bool] = False
    validate_output: Optional[bool] = True
    api_key: Optional[str] = None


async def stream_response(response: Stream[ChatCompletionChunk], request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
    """Stream the response from the LLM provider to the client"""

    first_chunk = {
        "docs": response.docs,
        "full_prompt": response.full_prompt,
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"

    full_msg = ""
    for chunk in response:
        if chunk.choices[0].finish_reason:
            # TODO: Send message about validation running
            # Then send a "fix" msg to let the client know the message needs to be replaced
            # In this case the client will still enable showing the old wrong msg by clicking on a card
            # if request.validate_output:
            #     messages.append(Message(role="assistant", content=full_msg))
            #     validate_and_fix_sparql(resp, response, request.model)
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
        full_msg += chunk.choices[0].delta.content
        yield f"data: {json.dumps(resp_chunk)}\n\n"


def extract_entities(sentence: str) -> list[dict[str, str]]:
    score_threshold = 0.8
    sentence_splitted = re.findall(r"\b\w+\b", sentence)
    window_size = len(sentence_splitted)
    entities_list = []
    while window_size > 0 and window_size <= len(sentence_splitted):
        window_start = 0
        window_end = window_start + window_size
        while window_end <= len(sentence_splitted):
            term = sentence_splitted[window_start:window_end]
            print("term", term)
            term_embeddings = next(iter(embedding_model.embed([" ".join(term)])))
            query_hits = vectordb.search(
                collection_name=settings.entities_collection_name,
                query_vector=term_embeddings,
                limit=10,
            )
            matchs = []
            for query_hit in query_hits:
                if query_hit.score > score_threshold:
                    matchs.append(query_hit)
            if len(matchs) > 0:
                entities_list.append(
                    {
                        "matchs": matchs,
                        "term": term,
                        "start_index": window_start,
                        "end_index": window_end,
                    }
                )
            # term_search = reduce(lambda x, y: "{} {}".format(x, y), sentence_splitted[window_start:window_end])
            # resultSearch = index.search(term_search)
            # if resultSearch is not None and len(resultSearch) > 0:
            #     selected_hit = resultSearch[0]
            #     if selected_hit['score'] > MAX_SCORE_PARSER_TRIPLES:
            #         selected_hit = None
            #     if selected_hit is not None and selected_hit not in matchs:
            #         matchs.append(selected_hit)
            window_start += 1
            window_end = window_start + window_size
        window_size -= 1
    return entities_list


@app.post("/chat")
async def chat(request: ChatCompletionRequest):
    if settings.expasy_api_key and request.api_key != settings.expasy_api_key:
        raise ValueError("Invalid API key")

    # print(client.models.list())
    # Remove any system prompt from the client request
    request.messages = [msg for msg in request.messages if msg.role != "system"]
    request.messages = [Message(role="system", content=settings.system_prompt), *request.messages]

    question: str = request.messages[-1].content if request.messages else ""
    query_embeddings = next(iter(embedding_model.embed([question])))
    logging.info(f"User question: {question}")

    # We build a big prompt with the most relevant queries retrieved from similarity search engine (could be increased)
    prompt = f"{STARTUP_PROMPT}\n\n"

    # # We also provide the example queries as previous messages to the LLM
    # system_msg: list[Message] = [{"role": "system", "content": settings.system_prompt}]

    # 1. Get the most relevant examples SPARQL queries from the search engine
    query_hits = vectordb.search(
        collection_name=settings.docs_collection_name,
        query_vector=query_embeddings,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
        limit=settings.retrieved_queries_count,
    )
    for query_hit in query_hits:
        prompt += f"{query_hit.payload['question']}:\n\n```sparql\n# {query_hit.payload['endpoint_url']}\n{query_hit.payload['answer']}\n```\n\n"
        # prompt += f"{query_hit.payload['question']}\nQuery to run in SPARQL endpoint {query_hit.payload['endpoint_url']}\n\n{query_hit.payload['answer']}\n\n"

    # 2. Get the most relevant documents other than SPARQL query examples from the search engine (ShEx shapes, general infos)
    docs_hits = vectordb.search(
        collection_name=settings.docs_collection_name,
        query_vector=query_embeddings,
        query_filter=Filter(
            should=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints classes schema"),
                ),
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="General information"),
                ),
                # NOTE: we don't add ontology documents yet, not clean enough
                # FieldCondition(
                #     key="doc_type",
                #     match=MatchValue(value="Ontology"),
                # ),
            ]
        ),
        limit=settings.retrieved_docs_count,
        # group_by="iri",
        # with_payload=True,
    )
    # TODO: vectordb.search_groups(
    # https://qdrant.tech/documentation/concepts/search/#search-groups
    # TODO: hybrid search? https://qdrant.github.io/fastembed/examples/Hybrid_Search/#about-qdrant
    # we might want to group by iri for shex docs https://qdrant.tech/documentation/concepts/hybrid-queries/?q=hybrid+se#grouping
    # https://qdrant.tech/documentation/concepts/search/#search-groups

    prompt += "Here is some additional information that could be useful to answer the user question:\n\n"
    # for docs_hit in docs_hits.groups:
    for docs_hit in docs_hits:
        if docs_hit.payload["doc_type"] == "SPARQL endpoints classes schema":
            prompt += f"ShEx shape for {docs_hit.payload['question']} in {docs_hit.payload['endpoint_url']}:\n```\n{docs_hit.payload['answer']}\n```\n\n"
        # elif docs_hit.payload["doc_type"] == "Ontology":
        #     prompt += f"Relevant part of the ontology for {docs_hit.payload['endpoint_url']}:\n```turtle\n{docs_hit.payload['question']}\n```\n\n"
        else:
            prompt += f"Information about: {docs_hit.payload['question']}\nRelated to SPARQL endpoint {docs_hit.payload['endpoint_url']}\n\n{docs_hit.payload['answer']}\n\n"

    # 3. Extract potential entities from the user question (experimental)
    # entities_list = extract_entities(question)
    # for entity in entities_list:
    #     prompt += f'\n\nEntities found in the user question for "{" ".join(entity["term"])}":\n\n'
    #     for match in entity["matchs"]:
    #         prompt += f"- {match.payload['label']} with IRI <{match.payload['uri']}> in endpoint {match.payload['endpoint_url']}\n\n"
    # if len(entities_list) == 0:
    #     prompt += "\nNo entities found in the user question that matches entities in the endpoints. "
    # prompt += "\nIf the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"

    # 4. Add the user question to the prompt
    prompt += f"\n{INTRO_USER_QUESTION_PROMPT}\n{question}"
    print(prompt)

    # Use messages from the request to keep memory of previous messages sent by the client
    # Replace the question asked by the user with the big prompt with all contextual infos
    request.messages[-1].content = prompt

    # Send the prompt to OpenAI to get a response
    # response = client.chat.completions.create(
    #     model=request.model,
    #     messages=request.messages,
    #     stream=request.stream,
    #     temperature=request.temperature,
    #     # response_format={ "type": "json_object" },
    # )
    # NOTE: to get response as JSON object check https://github.com/jxnl/instructor or https://github.com/outlines-dev/outlines

    # TODO: litellm
    response = completion(
        model=request.model,
        messages=request.messages,
        stream=request.stream,
    )

    # NOTE: the response is similar to OpenAI API, but we add the list of hits and the full prompt used to ask the question
    response.docs = [hit.model_dump() for hit in query_hits + docs_hits]
    response.full_prompt = prompt

    if request.stream:
        return StreamingResponse(
            stream_response(response, request), media_type="application/x-ndjson"
        )

    request.messages.append(Message(role="assistant", content=response.choices[0].message.content))
    # print(response)
    # print(response.choices[0].message.content)
    response: ChatCompletion = (
        validate_and_fix_sparql(request, response) if request.validate_output else response
    )
    return response
    # return {
    #     "id": response.id,
    #     "object": "chat.completion",
    #     "created": response.created,
    #     "model": response.model,
    #     "choices": [{"message": Message(role="assistant", content=response.choices[0].message.content)}],
    #     "docs": query_hits + docs_hits,
    #     "full_prompt": prompt,
    #     "usage": response.usage,
    # }


def validate_and_fix_sparql(
    request: ChatCompletionRequest, resp: ChatCompletion | None = None, try_count: int = 0
) -> ChatCompletion:
    """Recursive function to validate the SPARQL queries in the chat response and fix them if needed."""
    if try_count >= settings.max_try_fix_sparql:
        resp.choices[
            0
        ].message.content = f"{resp.choices[0].message.content}\n\nThe SPARQL query could not be fixed after multiple tries. Please do it yourself!"
        return resp
    # generated_sparqls = extract_sparql_queries(resp.choices[0].message.content)
    generated_sparqls = extract_sparql_queries(request.messages[-1].content)
    # print("generated_sparqls", generated_sparqls)
    error_detected = False
    for gen_query in generated_sparqls:
        try:
            translateQuery(parseQuery(gen_query["query"]))
            if gen_query["endpoint_url"]:
                issues = validate_sparql_with_void(gen_query["query"], gen_query["endpoint_url"], prefix_converter)
                if len(issues) > 0:
                    issues_str = "\n".join(issues)
                    raise ValueError(f"Validation issues:\n{issues_str}")
            else:
                print("Endpoint URL not provided with the query")

        except Exception as e:
            if "Unknown namespace prefix" in str(e):
                resp.choices[0].message.content = resp.choices[0].message.content.replace(
                    gen_query["query"], add_missing_prefixes(gen_query["query"], prefixes_map)
                )
            else:
                # Ask the LLM to try to fix it
                print(f"Error in SPARQL query try #{try_count}: {e}\n{gen_query['query']}")
                error_detected = True
                try_count += 1
                fix_prompt = f"""There is an error in the generated SPARQL query:
`{e}`

SPARQL query:
{gen_query["query"]}

Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.
"""
                # Which is part of this answer:
                # {md_resp}
                # messages.append({"role": "assistant", "content": fix_prompt})
                request.messages.append(Message(role="assistant", content=fix_prompt))
                # fixing_resp = client.chat.completions.create(
                #     model=llm_model,
                #     messages=messages,
                #     stream=False,
                # )
                fixing_resp = completion(
                    model=request.model,
                    messages=request.messages,
                    stream=False,
                )
                # md_resp = response.choices[0].message.content
                fixed_sparqls = extract_sparql_queries(fixing_resp.choices[0].message.content)
                for fixed_query in fixed_sparqls:
                    resp.usage.prompt_tokens += fixing_resp.usage.prompt_tokens
                    resp.usage.completion_tokens += fixing_resp.usage.completion_tokens
                    resp.usage.total_tokens += fixing_resp.usage.total_tokens
                    resp.choices[0].message.content = resp.choices[0].message.content.replace(
                        gen_query["query"], fixed_query["query"]
                    )
    if error_detected:
        # Check again the fixed query
        return validate_and_fix_sparql(request, resp, try_count)
    return resp


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

templates = Jinja2Templates(directory="src/sparql_llm/webapp")
app.mount(
    "/assets",
    StaticFiles(directory="src/sparql_llm/webapp/assets"),
    name="static",
)

# app.mount(
#     "/",
#     StaticFiles(
#         directory=pkg_resources.resource_filename("sparql_llm", "webapp"), html=True
#     ),
#     name="static",
# )

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def chat_ui(request: Request) -> Any:
    """Render the chat UI using jinja2 + HTML"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "expasy_key": settings.expasy_api_key,
            "api_url": "https://chat.expasy.org/",
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
