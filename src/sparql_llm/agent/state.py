"""Define the state structures for the agent."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from langchain.messages import AnyMessage
from langchain_core.documents import Document
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep
from pydantic import BaseModel, Field


# https://python.langchain.com/docs/how_to/structured_output
class StructuredQuestion(BaseModel):
    """Structured informations extracted from the user question."""

    intent: Literal["general_information", "access_resources"] = Field(
        default="access_resources",
        description="Intent extracted from the user question",
    )
    extracted_classes: list[str] = Field(
        default_factory=list,
        description="List of classes extracted from the user question",
    )
    extracted_entities: list[str] = Field(
        default_factory=list,
        description="List of entities extracted from the user question",
    )
    question_steps: list[str] = Field(
        default_factory=list,
        description="List of steps extracted from the user question",
    )


class StepOutput(BaseModel):
    """Represents a step the agent went through to generate the answer."""

    label: str
    """The human-readable title for this step to be displayed to the user."""

    details: str = Field(default="")
    """Details of the steps results in markdown to be displayed to the user. It can be either a markdown string or a list of StepOutput."""

    substeps: list[StepOutput] | None = Field(default_factory=lambda: [])
    """Optional substeps for a step."""

    type: Literal["context", "fix-message", "recall"] = Field(default="context")
    """The type of the step."""

    fixed_message: str | None = None
    """The fixed message to replace the last message sent to the user."""


@dataclass
class StructuredOutput:
    """Structure for structured infos extracted from the LLM output."""

    sparql_query: str
    sparql_endpoint_url: str


@dataclass
class InputState:
    """Defines the input state for the agent, representing a narrower interface to the outside world.

    This class is used to define the initial state and structure of incoming data.
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    """
    Messages tracking the primary execution state of the agent.

    Typically accumulates a pattern of:
    1. HumanMessage - user input
    2. AIMessage with .tool_calls - agent picking tool(s) to use to collect information
    3. ToolMessage(s) - the responses (or errors) from the executed tools
    4. AIMessage without .tool_calls - agent responding in unstructured format to the user
    5. HumanMessage - user responds with the next conversational turn

    Steps 2-5 may repeat as needed.

    The `add_messages` annotation ensures that new messages are merged with existing ones,
    updating by ID to maintain an "append-only" state unless a message with the same ID is provided.
    """


@dataclass
class State(InputState):
    """Represents the complete state of the agent, extending InputState with additional attributes.

    This class can be used to store any information needed throughout the agent's lifecycle.
    """

    is_last_step: IsLastStep = field(default=False)
    """Indicates whether the current step is the last one before the graph raises an error.

    This is a 'managed' variable, controlled by the state machine rather than user code.
    It is set to 'True' when the step count reaches recursion_limit - 1.
    """

    structured_question: StructuredQuestion = field(default_factory=StructuredQuestion)

    retrieved_docs: list[Document] = field(default_factory=list)
    extracted_entities: dict[str, Any] = field(default_factory=dict)
    passed_validation: bool = field(default=True)
    try_count: int = field(default=0)

    steps: Annotated[list[StepOutput], add_to_list] = field(default_factory=list)
    structured_output: list[StructuredOutput] = field(default_factory=list)


def add_to_list(original_list: list[Any], new_items: list[Any]) -> list[Any]:
    """We need to do this copy workaround to avoid mutable side effects that comes with LangGraph state"""
    new = original_list.copy()
    new.extend(new_items)
    return new
