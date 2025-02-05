"""Extract potential entities from the user question (experimental)."""
import re
from typing import Any

from langchain_core.runnables import RunnableConfig
from qdrant_client import QdrantClient
from sparql_llm.utils import get_message_text
import spacy

from expasy_agent.config import Configuration, get_embedding_model, settings
from expasy_agent.state import State


def format_extracted_entities(entities_list: list[Any]) -> str:
    if len(entities_list) == 0:
        return "No entities found in the user question that matches entities in the endpoints. "
    prompt = ""
    for entity in entities_list:
        prompt += f'\n\nEntities found in the user question for "{" ".join(entity["text"])}":\n\n'
        for match in entity["matchs"]:
            prompt += f"- {match.payload['label']} with IRI <{match.payload['uri']}> in endpoint {match.payload['endpoint_url']}\n\n"
        # prompt += "\nIf the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"
    return prompt



async def extract_entities(state: State, config: RunnableConfig) -> dict[str, list[Any]]:
    """Extract potential entities from the latest message in the state.

    This function takes the current state and configuration, uses the latest query
    from the state to extract relevant entities.

    Args:
        state (State): The current state containing queries and the retriever.
        config (RunnableConfig | None, optional): Configuration for the retrieval process.

    Returns:
        dict[str, list[Document]]: A dictionary with a single key "retrieved_docs"
        containing a list of retrieved Document objects.
    """
    user_input = get_message_text(state.messages[-1])

    vectordb = QdrantClient(url=settings.vectordb_url, prefer_grpc=True)
    embedding_model = get_embedding_model()
    score_threshold = 0.8
    entities_list = []

    # Extract potential entities with scispaCy https://allenai.github.io/scispacy/
    # NOTE: more expensive alternative could be to use the BioBERT model
    nlp = spacy.load("en_core_sci_md")
    potential_entities = nlp(user_input).ents
    print(potential_entities)

    # Search for matches in the indexed entities
    entities_embeddings = embedding_model.embed([entity.text for entity in potential_entities])
    for i, entity_embeddings in enumerate(entities_embeddings):
        query_hits = vectordb.search(
            collection_name=settings.entities_collection_name,
            query_vector=entity_embeddings,
            limit=10,
        )
        matchs = []
        for query_hit in query_hits:
            if query_hit.score > score_threshold:
                matchs.append(query_hit)
        entities_list.append(
            {
                "matchs": matchs,
                "text": potential_entities[i].text,
                # "start_index": None,
                # "end_index": None,
            }
        )
    return {"extracted_entities": entities_list}

    ## Using BioBERT
    # from transformers import AutoTokenizer, AutoModelForTokenClassification
    # from transformers import pipeline

    # # Load BioBERT model and tokenizer
    # model_name = "dmis-lab/biobert-v1.1"
    # tokenizer = AutoTokenizer.from_pretrained(model_name)
    # model = AutoModelForTokenClassification.from_pretrained(model_name)

    # # Create NER pipeline
    # ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

    # # Extract entities
    # results = ner_pipeline(user_input)
    # for entity in results:
    #     print(f"{entity['word']} ({entity['entity_group']})")

    ## Old way
    # sentence_splitted = re.findall(r"\b\w+\b", user_input)
    # window_size = len(sentence_splitted)
    # while window_size > 0 and window_size <= len(sentence_splitted):
    #     window_start = 0
    #     window_end = window_start + window_size
    #     while window_end <= len(sentence_splitted):
    #         term = sentence_splitted[window_start:window_end]
    #         # print("term", term)
    #         term_embeddings = next(iter(embedding_model.embed([" ".join(term)])))
    #         query_hits = vectordb.search(
    #             collection_name=settings.entities_collection_name,
    #             query_vector=term_embeddings,
    #             limit=10,
    #         )
    #         matchs = []
    #         for query_hit in query_hits:
    #             if query_hit.score > score_threshold:
    #                 matchs.append(query_hit)
    #         if len(matchs) > 0:
    #             entities_list.append(
    #                 {
    #                     "matchs": matchs,
    #                     "term": term,
    #                     "start_index": window_start,
    #                     "end_index": window_end,
    #                 }
    #             )
    #         # term_search = reduce(lambda x, y: "{} {}".format(x, y), sentence_splitted[window_start:window_end])
    #         # resultSearch = index.search(term_search)
    #         # if resultSearch is not None and len(resultSearch) > 0:
    #         #     selected_hit = resultSearch[0]
    #         #     if selected_hit['score'] > MAX_SCORE_PARSER_TRIPLES:
    #         #         selected_hit = None
    #         #     if selected_hit is not None and selected_hit not in matchs:
    #         #         matchs.append(selected_hit)
    #         window_start += 1
    #         window_end = window_start + window_size
    #     window_size -= 1
