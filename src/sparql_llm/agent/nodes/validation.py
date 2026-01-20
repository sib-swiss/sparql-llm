"""Validate output of a LLM, e.g. SPARQL queries generated."""

import json
import re
from typing import Any

from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from sparql_llm.agent.prompts import FIX_QUERY_PROMPT
from sparql_llm.agent.state import State, StepOutput
from sparql_llm.config import Configuration, settings
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints, query_sparql
from sparql_llm.validate_sparql import validate_sparql_in_msg

prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(settings.endpoints)


async def validate_output(state: State, config: RunnableConfig) -> dict[str, Any]:
    """LangGraph node to validate the output of a LLM call, e.g. SPARQL queries generated.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)
    if not configuration.enable_output_validation:
        return {}
    # Remove the thought process <think> tags from the last message
    last_msg = re.sub(r"<think>.*?</think>", "", str(state.messages[-1].content), flags=re.DOTALL)
    validation_steps: list[StepOutput] = []
    recall_messages: list[HumanMessage] = []

    validation_outputs = validate_sparql_in_msg(last_msg, prefixes_map, endpoints_void_dict)
    for validation_output in validation_outputs:
        if validation_output["fixed_query"]:
            # Pass the fixed msg to the client
            validation_steps.append(
                StepOutput(
                    type="fix-message",
                    label="✅ Fixed the prefixes of the generated SPARQL query automatically",
                    details=f"Prefixes corrected from the query generated in the original response.\n### Original response\n{last_msg}",
                    fixed_message=last_msg.replace(
                        validation_output["original_query"],
                        validation_output["fixed_query"],
                    ),
                )
            )
        if validation_output["errors"]:
            # Recall the LLM to try to fix errors
            error_str = "- " + "\n- ".join(validation_output["errors"])
            validation_msg = f"The query generated in the original response is not valid according to the endpoints schema.\n### Validation results\n{error_str}\n### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```\n### Original response\n{last_msg}\n"
            validation_steps.append(
                StepOutput(
                    type="recall",
                    label="🐞 Generated query invalid, fixing it",
                    details=validation_msg,
                )
            )
            # Add a new message to ask the model to fix the error
            recall_messages.append(
                HumanMessage(
                    content=f"Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n\nSPARQL query: {validation_output['original_query']}\n\nError messages:\n{error_str}",
                    # name="recall",
                    # additional_kwargs={"validation_results": error_str},
                )
            )

    response = {
        "steps": validation_steps,
        "messages": recall_messages,
        "try_count": state.try_count + 1 if recall_messages else state.try_count,
        "passed_validation": not recall_messages,
    }
    extracted = {}
    # Add structured output if a valid query was generated
    if validation_outputs and not recall_messages:
        if validation_outputs[-1].get("fixed_query"):
            extracted["sparql_query"] = validation_outputs[-1]["fixed_query"]
        else:
            extracted["sparql_query"] = validation_outputs[-1]["original_query"]
        if validation_outputs[-1]["endpoint_url"]:
            extracted["sparql_endpoint_url"] = validation_outputs[-1]["endpoint_url"]
        response["structured_output"] = extracted

        # Automatically execute the SPARQL query
        if configuration.enable_sparql_execution and not settings.use_tools:
            sparql_query = extracted.get("sparql_query")
            endpoint_url = extracted.get("sparql_endpoint_url")
            if sparql_query and endpoint_url:
                execute_resp = ""
                try:
                    res = query_sparql(
                        sparql_query,
                        endpoint_url,
                        timeout=10,
                        check_service_desc=False,
                        post=False,
                    )
                    res_bindings = res.get("results", {}).get("bindings", [])
                    if len(res_bindings) == 0:
                        # If no results, return a message to ask fix the query
                        execute_resp = f"Query on {endpoint_url} returned no results. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
                    elif res_bindings and len(res_bindings) > 50:
                        # Truncate the results if too large
                        execute_resp = f"Executed query on {endpoint_url}:\n```sparql\n{sparql_query}\n```\n\nResults (showing first 50 out of {len(res_bindings)} results):\n```\n{json.dumps(res_bindings[:200], indent=2)}\n```"
                    else:
                        execute_resp = f"Executed query on {endpoint_url}:\n```sparql\n{sparql_query}\n```\n\nResults:\n```\n{json.dumps(res, indent=2)}\n```"
                except Exception as e:
                    execute_resp = f"Query on {endpoint_url} returned error:\n\n{e}\n\n{FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
                # print("EXECUTE RESP", execute_resp)
                recall_messages.append(
                    # FunctionMessage(
                    HumanMessage(
                        content=execute_resp,
                        name="execute_sparql_query",
                    )
                )
                response["messages"] = recall_messages
                response["passed_validation"] = False
                response["try_count"] = state.try_count + 1
                validation_steps.append(
                    StepOutput(
                        type="recall",
                        label="⚡️ SPARQL query executed, see raw results",
                        details=execute_resp,
                    )
                )
                response["steps"] = validation_steps
    return response
