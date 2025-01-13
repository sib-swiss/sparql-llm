"""Validate output of a LLM, e.g. SPARQL queries generated."""

from collections import defaultdict
from typing import Any, Optional, Union

from langchain_core.messages import AIMessage
from rdflib.plugins.sparql import prepareQuery
from sparql_llm.utils import (
    get_prefix_converter,
    get_prefixes_for_endpoints,
)
from sparql_llm.validate_sparql import (
    add_missing_prefixes,
    extract_sparql_queries,
    validate_sparql_with_void,
)

from expasy_agent.config import settings
from expasy_agent.state import State


async def validate_sparql(state: State) -> dict[str, list[AIMessage]]:
    """Validate output of a LLM, e.g. SPARQL queries generated.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    last_msg = state.messages[-1]
    responses = []
    generated_sparqls = extract_sparql_queries(last_msg.content)
    for gen_query in generated_sparqls:
        sparql_issues = []
        errors = []
        # last_msg.additional_kwargs = {"extracted": {"sparql_query": gen_query["query"], "sparql_endpoint_url": gen_query["endpoint_url"]}}
        try:
            # Try to parse, to fix prefixes and rare structural issues
            prepareQuery(gen_query["query"])
        except Exception as e:
            if "Unknown namespace prefix" in str(e):
                # Automatically fix the prefixes
                fixed_query = add_missing_prefixes(gen_query["query"], prefixes_map)
                fixed_msg = last_msg.content.replace(gen_query["query"], fixed_query)
                gen_query["query"] = fixed_query
                # Pass the fixed msg to the client
                responses.append(AIMessage(content=fixed_msg, name="fix-prefixes"))
                # Check if other errors are present
                errors = [line for line in str(e).splitlines() if "Unknown namespace prefix" not in line]
        # Validate the SPARQL query based on schema from VoID description
        if gen_query["endpoint_url"] and not errors:
            sparql_issues = validate_sparql_with_void(gen_query["query"], gen_query["endpoint_url"], prefix_converter)
            errors = errors + list(sparql_issues)
        if errors:
            # Ask the LLM to try to fix it
            # https://python.langchain.com/api_reference/core/messages/langchain_core.messages.ai.AIMessage.html
            validation_msg = "- " + "\n- ".join(errors)
            responses.append(AIMessage(
                content=f"Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n\nSPARQL query: {gen_query['query']}\n\nError messages:\n{validation_msg}",
                name="recall-model",
                additional_kwargs={"validation_results": validation_msg},
            ))

    resp = {"messages": responses, "try_count": state.try_count+1}
    # resp["validation_results"] = {"message": validation_msg, "recall": True}
    extracted = {}
    if generated_sparqls:
        if generated_sparqls[-1]["query"]:
            extracted["sparql_query"] = generated_sparqls[-1]["query"]
        if generated_sparqls[-1]["endpoint_url"]:
            extracted["sparql_endpoint_url"] = generated_sparqls[-1]["endpoint_url"]
    if extracted:
        resp["extracted_entities"] = extracted
    # Return the model's response as a list to be added to existing messages
    return resp


# TODO: get endpoints config
prefixes_map = get_prefixes_for_endpoints([endpoint["endpoint_url"] for endpoint in settings.endpoints])
prefix_converter = get_prefix_converter(prefixes_map)
