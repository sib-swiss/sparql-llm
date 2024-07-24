import re

queries_pattern = re.compile(r"```sparql(.*?)```", re.DOTALL)
endpoint_pattern = re.compile(r"^#.*(https?://[^\s]+)", re.MULTILINE)

def extract_sparql_queries(md_resp: str) -> list[dict[str, str]]:
    """Extract SPARQL queries and endpoint URL from a markdown response."""
    extracted_queries = []
    queries = queries_pattern.findall(md_resp)
    for query in queries:
        extracted_endpoint = endpoint_pattern.search(query.strip())
        extracted_queries.append({
            "query": query.strip(),
            "endpoint": extracted_endpoint if extracted_endpoint else None,
        })
    return extracted_queries
