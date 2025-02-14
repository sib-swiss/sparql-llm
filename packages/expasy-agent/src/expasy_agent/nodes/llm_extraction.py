"""Node to call the model.

Works with a chat model with tool calling support.
"""

from typing import Dict, List, Literal

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from expasy_agent.config import Configuration
from expasy_agent.prompts import EXTRACTION_PROMPT
from expasy_agent.state import State, StepOutput
from expasy_agent.utils import load_chat_model


# https://python.langchain.com/docs/how_to/structured_output
class StructuredQuestion(BaseModel):
    """Extracted."""

    intent: Literal["general_information", "access_resources"] = Field(
        description="Intent extracted from the user question"
    )
    extracted_classes: list[str] = Field(
        description="List of classes extracted from the user question"
    )
    extracted_entities: list[str] = Field(
        description="List of entities extracted from the user question"
    )
    question_steps: list[str] = Field(
        default_factory=list,
        description="List of steps extracted from the user question",
    )


async def extract_user_question(
    state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)

    model = load_chat_model(configuration).with_structured_output(StructuredQuestion)

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", EXTRACTION_PROMPT),
            ("placeholder", "{messages}"),
        ]
    )
    message_value = await prompt_template.ainvoke(
        {
            "messages": state.messages,
        },
        config,
    )

    # print(message_value)
    # print(message_value.messages[0].content)
    structured_question: StructuredQuestion = await model.ainvoke(
        message_value, {**config, "configurable": {"stream": False}}
    )

    # print(structured_question)

    return {
        "structured_question": structured_question,
        "steps": [
            StepOutput(
                label=f"⚗️ Extracted {len(structured_question.question_steps)} steps and {len(structured_question.extracted_classes)} classes",
                details=f"""Intent: {structured_question.intent.replace("_", " ")}

Steps to answer the user question:

{chr(10).join(f"- {step}" for step in structured_question.question_steps)}

Potential classes:

{chr(10).join(f"- {cls}" for cls in structured_question.extracted_classes)}

Potential entities:

{chr(10).join(f"- {entity}" for entity in structured_question.extracted_entities)}""",
            )
        ],
    }
