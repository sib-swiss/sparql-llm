"""Extract potential entities from the user question (experimental)."""

from typing import Any

from fastembed import SparseTextEmbedding
from langchain_core.runnables import RunnableConfig
from qdrant_client import models

from sparql_llm.agent.state import State, StepOutput
from sparql_llm.config import Configuration, embedding_model, qdrant_client, settings

# NOTE: experimental, not used in production


def format_extracted_entities(entities_list: list[Any]) -> str:
    if len(entities_list) == 0:
        return "No entities found in the user question that matches entities in the endpoints. "
    prompt = "\nHere are entities extracted from the user question that could be find in the endpoints. If the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"
    for entity in entities_list:
        prompt += f'\n\nEntities found in the user question for "{entity["text"]}":\n\n'
        for scored_point in entity["matchs"]:
            payload = scored_point.payload or {}
            prompt += f"- `{scored_point.score or 0:.2f}` {payload.get('label', '')} with IRI <{payload.get('uri', '')}> in endpoint {payload.get('endpoint_url', '')}\n\n"
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

    # Initialize embedding models
    sparse_embedding_model = SparseTextEmbedding(settings.sparse_embedding_model)

    # Generate embeddings for all entities in batch for better performance
    potential_entities = state.structured_question.extracted_entities
    dense_embeddings = list(embedding_model.embed(potential_entities))
    sparse_embeddings = list(sparse_embedding_model.embed(potential_entities))

    # Search for matches in the indexed entities
    for idx, potential_entity in enumerate(potential_entities):
        query_dense_embedding = dense_embeddings[idx].tolist()
        query_sparse_embedding_raw = sparse_embeddings[idx]

        # Convert sparse embedding to SparseVector format
        query_sparse_embedding = models.SparseVector(
            indices=query_sparse_embedding_raw.indices.tolist(),
            values=query_sparse_embedding_raw.values.tolist(),
        )

        # Perform hybrid search using query_points with RRF fusion
        results = qdrant_client.query_points(
            collection_name=settings.entities_collection_name,
            prefetch=[
                models.Prefetch(
                    using="",
                    query=query_dense_embedding,
                    limit=results_count,
                ),
                models.Prefetch(
                    using="sparse",
                    query=query_sparse_embedding,
                    limit=results_count,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=results_count,
        ).points

        matchs: list[models.ScoredPoint] = []
        for scored_point in results:
            payload = scored_point.payload or {}
            # Check if this URI + endpoint combination already exists in matches
            is_duplicate = any(
                (m.payload or {}).get("uri") == payload.get("uri")
                and (m.payload or {}).get("endpoint_url") == payload.get("endpoint_url")
                for m in matchs
            )
            if not is_duplicate:
                matchs.append(scored_point)
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
