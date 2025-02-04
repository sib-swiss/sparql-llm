"""Validate output of a LLM, e.g. SPARQL queries generated."""

import re
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
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

from expasy_agent.config import Configuration, settings
from expasy_agent.state import State, ValidationState


async def validate_output(state: State, config: RunnableConfig) -> dict[str, Any]:
    """LangGraph node to validate the output of a LLM call, e.g. SPARQL queries generated.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)
    if not configuration.validate_output:
        return {}
    # Remove the thought process <think> tags from the last message
    last_msg = re.sub(r"<think>.*?</think>", "", state.messages[-1].content, flags=re.DOTALL)
    validation_results = []
    new_messages = []
    generated_sparqls = extract_sparql_queries(last_msg)
    for gen_query in generated_sparqls:
        errors = []
        # 1. Check if the query is syntactically valid, auto fix prefixes when possible
        try:
            # Try to parse, to fix prefixes and structural issues
            prepareQuery(gen_query["query"])
        except Exception as e:
            if "Unknown namespace prefix" in str(e):
                # Automatically fix missing prefixes
                fixed_query = add_missing_prefixes(gen_query["query"], prefixes_map)
                fixed_msg = last_msg.replace(gen_query["query"], fixed_query)
                gen_query["query"] = fixed_query
                # Pass the fixed msg to the client
                validation_results.append(ValidationState(
                    type="prefixes",
                    label="✅ Fixed the prefixes of the generated SPARQL query automatically",
                    details=f"Prefixes corrected from the query generated in the original response.\n### Original response\n{last_msg}",
                    fixed_message=fixed_msg,
                ))
                # Check if other errors are present
                errors = [line for line in str(e).splitlines() if "Unknown namespace prefix" not in line]

        # 2. Validate the SPARQL query based on schema from VoID description
        if gen_query["endpoint_url"] and not errors:
            errors = list(validate_sparql_with_void(gen_query["query"], gen_query["endpoint_url"], prefix_converter))

        # 3. Recall the LLM to try to fix errors
        if errors:
            error_str = "- " + "\n- ".join(errors)
            validation_msg = f"The query generated in the original response is not valid according to the endpoints schema.\n### Validation results\n{error_str}\n### Erroneous SPARQL query\n```sparql\n{gen_query['query']}\n```\n### Original response\n{last_msg}\n"
            validation_results.append(ValidationState(
                type="recall",
                label="🐞 Generated query invalid, fixing it",
                details=validation_msg,
            ))
            # Add a new message to ask the model to fix the error
            new_messages.append(HumanMessage(
                content=f"Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n\nSPARQL query: {gen_query['query']}\n\nError messages:\n{error_str}",
                name="recall",
                # additional_kwargs={"validation_results": error_str},
            ))

    # TODO: add warning that we could not fix the issues
    # if state.try_count > configuration.max_try_fix_sparql and errors:

    response = {"validation": validation_results, "messages": new_messages, "try_count": state.try_count+1}
    extracted = {}
    if generated_sparqls:
        if generated_sparqls[-1]["query"]:
            extracted["sparql_query"] = generated_sparqls[-1]["query"]
        if generated_sparqls[-1]["endpoint_url"]:
            extracted["sparql_endpoint_url"] = generated_sparqls[-1]["endpoint_url"]
    if extracted:
        response["structured_output"] = extracted
    return response


# Retrieve the prefixes map and initialize converter from the endpoints defined in settings
prefixes_map = get_prefixes_for_endpoints([endpoint["endpoint_url"] for endpoint in settings.endpoints])
prefix_converter = get_prefix_converter(prefixes_map)
