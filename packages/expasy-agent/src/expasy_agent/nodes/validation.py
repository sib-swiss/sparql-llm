"""Validate output of a LLM, e.g. SPARQL queries generated."""

import re
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints
from sparql_llm.validate_sparql import validate_sparql_in_msg

from expasy_agent.config import Configuration, settings
from expasy_agent.state import State, StepOutput


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
    last_msg = re.sub(
        r"<think>.*?</think>", "", state.messages[-1].content, flags=re.DOTALL
    )
    validation_steps: list[StepOutput] = []
    recall_messages = []

    validation_outputs = validate_sparql_in_msg(
        last_msg, prefixes_map, endpoints_void_dict
    )
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
        "try_count": state.try_count + 1,
        "passed_validation": not recall_messages,
    }
    extracted = {}
    # Add structured output if a valid query was generated
    if validation_outputs:
        if validation_outputs[-1].get("fixed_query"):
            extracted["sparql_query"] = validation_outputs[-1]["fixed_query"]
        else:
            extracted["sparql_query"] = validation_outputs[-1]["original_query"]
        if validation_outputs[-1]["endpoint_url"]:
            extracted["sparql_endpoint_url"] = validation_outputs[-1]["endpoint_url"]
        response["structured_output"] = extracted
    return response


prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(settings.endpoints)
