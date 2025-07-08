import pandas as pd
from sparql_llm.utils import query_sparql

ENDPOINT_URL = 'http://localhost:8890/sparql/'

CLASS_QUERY = """
SELECT ?class (COUNT(*) AS ?count)
WHERE {
  [] a ?class .
  FILTER(?class != <http://www.w3.org/2002/07/owl#Thing>)
}
GROUP BY ?class
"""

PREDICATE_QUERY = """
SELECT ?class ?predicate (COUNT(*) AS ?count)
WHERE {{
[] a <{class_name}> ;
    ?predicate [] .
    FILTER(?predicate != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
}}
GROUP BY ?class ?predicate
"""


def get_class_info(probability_threshold: float = 0) -> pd.DataFrame:
    """Get class information from the SPARQL endpoint."""

    classes = query_sparql(CLASS_QUERY, endpoint_url=ENDPOINT_URL)['results']['bindings']
    classes = pd.DataFrame(classes).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
    classes['probability'] = round(classes['count'] / classes['count'].sum(), 3)
    classes = classes[classes['probability'] > probability_threshold].sort_values(by='probability', ascending=False).reset_index(drop=True)
    
    classes['predicates'] = classes['class'].apply(lambda c: get_class_predicates(c, probability_threshold))
    return classes


def get_class_predicates(class_name: str, probability_threshold: float = 0) -> dict[str, float]:
    """Get the predicates for a given class from the SPARQL endpoint."""

    predicates = query_sparql(PREDICATE_QUERY.format(class_name=class_name), endpoint_url=ENDPOINT_URL)['results']['bindings']
    predicates = pd.DataFrame(predicates).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
    predicates['probability'] = round(predicates['count'] / predicates['count'].sum(), 3)
    predicates = predicates[predicates['probability'] > probability_threshold].sort_values(by='probability', ascending=False).reset_index(drop=True)

    return dict(zip(predicates['predicate'], predicates['probability']))


if __name__ == "__main__":
    # Example usage
    print("Fetching class information...")
    class_info = get_class_info()
