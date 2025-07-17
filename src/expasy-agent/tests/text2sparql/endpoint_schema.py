import logging
import re
import pandas as pd
from sparql_llm.utils import query_sparql
from tqdm import tqdm
import time

tqdm.pandas()
logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)

CLASS_QUERY = """
SELECT ?class (COUNT(?class) AS ?count)
WHERE { 
    [] a ?class . 
}
GROUP BY ?class
ORDER BY DESC(?count)
"""

PREDICATE_QUERY = """
SELECT ?predicate (COUNT(?predicate) AS ?count)
WHERE {{
    [] a <{class_name}> ;
        ?predicate [] .
}}
GROUP BY ?predicate
ORDER BY DESC(?count)
"""

DATATYPE_QUERY = """
SELECT ?range
WHERE {{
    [] a <{class_name}> ;
         <{predicate_name}> ?o .
         BIND(datatype(?o) AS ?range)
}}
GROUP BY ?range
ORDER BY DESC(COUNT(?range))
LIMIT 1
"""

EXCLUDED_CLASSES = [
    'http://www.w3.org/2002/07/owl#Thing',
    ]
EXCLUDED_PREDICATES = [
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
]

def get_class_info(endpoint_url: str, probability_threshold: float = 0) -> pd.DataFrame:
    """Get class information from the SPARQL endpoint."""

    logger.info(f'Fetching class information from {endpoint_url}...')
    classes = query_sparql(CLASS_QUERY, endpoint_url=endpoint_url)['results']['bindings']
    classes = pd.DataFrame(classes).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
    classes = classes[~classes['class'].isin(EXCLUDED_CLASSES)]
    classes['name'] = classes['class'].apply(lambda c: re.sub(r'(?<!^)(?=[A-Z])', ' ', c.split('/')[-1].split('#')[-1]))
    classes['probability'] = round(classes['count'] / classes['count'].sum(), 3)
    classes = classes[classes['probability'] > probability_threshold].sort_values(by='probability', ascending=False).reset_index(drop=True)
    logger.info(f'Fetching predicate information from {endpoint_url}...')
    classes['predicates'] = classes['class'].progress_apply(lambda c: get_class_predicates(endpoint_url=endpoint_url, class_name=c, probability_threshold=probability_threshold))
    return classes


def get_class_predicates(endpoint_url: str, class_name: str, probability_threshold: float = 0) -> dict[str, float]:
    """Get the predicates for a given class from the SPARQL endpoint."""

    predicates = query_sparql(PREDICATE_QUERY.format(class_name=class_name), endpoint_url=endpoint_url)['results']['bindings']
    predicates = pd.DataFrame(predicates).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
    predicates = predicates[~predicates['predicate'].isin(EXCLUDED_PREDICATES)]
    predicates['probability'] = round(predicates['count'] / predicates['count'].sum(), 3)
    predicates = predicates[predicates['probability'] > probability_threshold].sort_values(by='probability', ascending=False).reset_index(drop=True)

    predicates['range'] = predicates['predicate'].apply(lambda p: query_sparql(DATATYPE_QUERY.format(class_name=class_name, predicate_name=p), endpoint_url=endpoint_url)['results']['bindings'][0])
    predicates['range'] = predicates['range'].apply(lambda r: r['range']['value'] if 'range' in r.keys() else None)

    return predicates.set_index('predicate')['range'].to_dict()


if __name__ == "__main__":
    endpoint_url = 'http://localhost:8890/sparql/'
    start_time = time.time()
    # class_info = get_class_info(endpoint_url=endpoint_url)
    l = get_class_predicates(endpoint_url=endpoint_url, class_name='http://xmlns.com/foaf/0.1/Person', probability_threshold=0.01)
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time / 60:.2f} minutes")