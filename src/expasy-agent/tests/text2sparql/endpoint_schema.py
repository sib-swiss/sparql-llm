import logging
import re
import pandas as pd
from sparql_llm.utils import query_sparql
import time
from joblib import Parallel, delayed
from tqdm import tqdm

logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)

TOP_N_PREDICATES = 20
TOP_CLASSES_PERCENTILE = .90

CLASS_QUERY = """
SELECT ?class (COUNT(?class) AS ?count)
WHERE { 
    ?s a ?class .
}
GROUP BY ?class
"""

PREDICATE_QUERY = """
SELECT ?predicate (COUNT(?predicate) AS ?count)
WHERE {{
    ?s a <{class_name}> ;
        ?predicate ?o .
}}
GROUP BY ?predicate
ORDER BY DESC(?count)
LIMIT {limit}
"""

DATATYPE_QUERY = """
SELECT (datatype(?o) AS ?range)
WHERE {{
    ?s a <{class_name}> ;
         <{predicate_name}> ?o .
         FILTER (isLiteral(?o)) .
}}
GROUP BY ?o
ORDER BY DESC(COUNT(?o))
LIMIT 1
"""

EXCLUDED_CLASSES = [
    'http://www.w3.org/2002/07/owl#Thing',
    ]
EXCLUDED_PREDICATES = [
]

def get_class_info(endpoint_url: str, max_workers: int = 4) -> pd.DataFrame:
    """Get class information from the SPARQL endpoint."""

    logger.info(f'Fetching class information from {endpoint_url}...')
    classes = query_sparql(CLASS_QUERY, endpoint_url=endpoint_url)['results']['bindings']
    classes = pd.DataFrame(classes).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
    classes = classes[~classes['class'].isin(EXCLUDED_CLASSES)]
    classes['name'] = classes['class'].apply(lambda c: re.sub(r'(?<!^)(?=[A-Z])', ' ', c.split('/')[-1].split('#')[-1]))

    num_classes = len(classes) 
    count_threshold = classes['count'].quantile(TOP_CLASSES_PERCENTILE)
    classes = classes[classes['count'] >= count_threshold].sort_values(by='count', ascending=False).reset_index(drop=True)
    logger.info(f'Keeping {len(classes)}/{num_classes} most frequent classes.')

    logger.info(f'Fetching predicate information from {endpoint_url}...')
    # classes['predicates'] = classes['class'].apply(lambda c: get_class_predicates(endpoint_url=endpoint_url, class_name=c))
    classes['predicates'] = Parallel(n_jobs=max_workers)(delayed(get_class_predicates)(endpoint_url=endpoint_url, class_name=c) for c in tqdm(classes['class'].tolist(), total=len(classes)))

    return classes


def get_class_predicates(endpoint_url: str, class_name: str) -> dict[str, str]:
    """Get the predicates and their ranges for a given class from the SPARQL endpoint."""

    predicates = query_sparql(PREDICATE_QUERY.format(class_name=class_name, limit=TOP_N_PREDICATES), endpoint_url=endpoint_url)['results']['bindings']
    predicates = pd.DataFrame(predicates).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
    predicates = predicates[~predicates['predicate'].isin(EXCLUDED_PREDICATES)]
    
    predicates['range'] = predicates['predicate'].apply(lambda p: (query_sparql(DATATYPE_QUERY.format(class_name=class_name, predicate_name=p), endpoint_url=endpoint_url)['results']['bindings'] or [{}])[0])
    predicates['range'] = predicates['range'].apply(lambda r: r['range']['value'] if 'range' in r.keys() else pd.NA)
    predicates = predicates.dropna(subset=['range'])

    return predicates.set_index('predicate')['range'].to_dict()


if __name__ == "__main__":
    endpoint_url = 'http://localhost:8890/sparql/'
    max_workers = 4
    start_time = time.time()
    class_info = get_class_info(endpoint_url=endpoint_url, max_workers=max_workers)
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time / 60:.2f} minutes")