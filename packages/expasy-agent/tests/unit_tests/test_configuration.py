from sparql_llm.langgraph.config import SparqlAgentConfiguration


def test_configuration_empty() -> None:
    SparqlAgentConfiguration.from_runnable_config({})
