"""Extract potential entities from the user question (experimental)."""

from typing import Any

from langchain_core.runnables import RunnableConfig

from sparql_llm.agent.state import State, StepOutput
from sparql_llm.config import Configuration
from sparql_llm.vectordb import search_entities

# NOTE: experimental, not used in production


def format_extracted_entities(entities_list: list[Any]) -> str:
    if len(entities_list) == 0:
        return "No entities found in the user question that matches entities in the endpoints. "
    prompt = "\nHere are entities extracted from the user question that could be find in the endpoints. If the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"
    for entity in entities_list:
        prompt += f'\n\nEntities found in the user question for "{entity["text"]}":\n\n'
        for match in entity["matchs"]:
            prompt += f"- `{match['_relevance_score']:.2f}` {match['label']} with IRI <{match['iri']}> in endpoint {match['endpoint_url']}\n\n"
        # prompt += "\nIf the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"
    return prompt


async def resolve_entities(state: State, config: RunnableConfig) -> dict[str, list[Any]]:
    """Resolve potential entities from the latest message in the state.

    This function takes the current state and configuration, uses the latest query
    from the state to resolve relevant entities and link them to URIs from the endpoints.

    Args:
        state (State): The current state containing queries and the retriever.
        config (RunnableConfig | None, optional): Configuration for the retrieval process.

    Returns:
        dict[str, list[Document]]: A dictionary with a single key "retrieved_docs"
        containing a list of retrieved Document objects.
    """
    configuration = Configuration.from_runnable_config(config)
    if configuration.enable_entities_resolution is False:
        return {}

    # Extract potential entities with sciSpaCy https://allenai.github.io/scispacy/
    # A more expensive alternative could be to use the BioBERT model
    # import spacy
    # user_input = get_message_text(state.messages[-1])
    # nlp: spacy.Language = spacy.load("en_core_sci_md")
    # potential_entities = nlp(user_input).ents
    # print(potential_entities)

    # Search for matches in the indexed entities
    potential_entities = state.structured_question.extracted_entities
    entities_list = [
        {"matchs": matchs, "text": text}
        for text, matchs in zip(potential_entities, search_entities(potential_entities), strict=True)
    ]
    return {
        "extracted_entities": entities_list,
        "steps": [
            StepOutput(
                label=f"🖇️ Linked {len(entities_list)} potential entities",
                details=format_extracted_entities(entities_list),
            )
        ],
    }
