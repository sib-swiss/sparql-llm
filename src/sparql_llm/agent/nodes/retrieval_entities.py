"""Extract potential entities from the user question (experimental)."""

from typing import Any

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.runnables import RunnableConfig
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode

from sparql_llm.agent.config import Configuration, qdrant_client, settings
from sparql_llm.agent.state import State, StepOutput

# NOTE: experimental, not used in production


def format_extracted_entities(entities_list: list[Any]) -> str:
    if len(entities_list) == 0:
        return "No entities found in the user question that matches entities in the endpoints. "
    prompt = "\nHere are entities extracted from the user question that could be find in the endpoints. If the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"
    for entity in entities_list:
        prompt += f'\n\nEntities found in the user question for "{entity["text"]}":\n\n'
        for match in entity["matchs"]:
            prompt += f"- `{match.metadata['score']:.2f}` {match.metadata['label']} with IRI <{match.metadata['uri']}> in endpoint {match.metadata['endpoint_url']}\n\n"
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

    results_count = 5
    # score_threshold = 0.8 # Does not work well with sparse embeddings
    entities_list = []

    # Extract potential entities with sciSpaCy https://allenai.github.io/scispacy/
    # A more expensive alternative could be to use the BioBERT model
    # import spacy
    # user_input = get_message_text(state.messages[-1])
    # nlp: spacy.Language = spacy.load("en_core_sci_md")
    # potential_entities = nlp(user_input).ents
    # print(potential_entities)

    vectordb = QdrantVectorStore(
        client=qdrant_client,
        # url=settings.vectordb_url,
        # prefer_grpc=True,
        collection_name=settings.entities_collection_name,
        embedding=FastEmbedEmbeddings(model_name=settings.embedding_model),
        sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
        retrieval_mode=RetrievalMode.HYBRID,
    )

    # Search for matches in the indexed entities
    for potential_entity in state.structured_question.extracted_entities:
        # for potential_entity in potential_entities:
        query_hits = vectordb.similarity_search_with_score(
            query=potential_entity,
            k=results_count,
            # score_threshold=score_threshold,
        )
        matchs = []
        for doc, score in query_hits:
            # print(f"* [SIM={score:.3f}] {doc.page_content} [{doc.metadata}]")
            # Check if this URI + endpoint combination already exists in matches
            is_duplicate = any(
                m.metadata["uri"] == doc.metadata["uri"] and m.metadata["endpoint_url"] == doc.metadata["endpoint_url"]
                for m in matchs
            )
            if not is_duplicate:
                doc.metadata["score"] = score
                matchs.append(doc)
        entities_list.append(
            {
                "matchs": matchs,
                "text": potential_entity,
                # "start_index": None,
                # "end_index": None,
            }
        )
    return {
        "extracted_entities": entities_list,
        "steps": [
            StepOutput(
                label=f"🖇️ Linked {len(entities_list)} potential entities",
                details=format_extracted_entities(entities_list),
            )
        ],
    }
