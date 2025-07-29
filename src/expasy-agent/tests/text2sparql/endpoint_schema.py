import logging
import re
import pandas as pd
from sparql_llm.utils import query_sparql
import time
from joblib import Parallel, delayed
from tqdm import tqdm

logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)

class EndpointSchema:
    CLASS_QUERY = """
    SELECT ?class (COUNT(?class) AS ?count)
    FROM <{graph}>
    WHERE {{
        ?s a ?class .
    }}
    GROUP BY ?class
    """

    PREDICATE_QUERY = """
    SELECT ?predicate (COUNT(?predicate) AS ?count)
    FROM <{graph}>
    WHERE {{
        ?s a <{class_name}> ;
            ?predicate ?o .
    }}
    GROUP BY ?predicate
    ORDER BY DESC(?count)
    LIMIT {limit}
    """

    RANGE_DATATYPE_QUERY = """
    SELECT ?range
    FROM <{graph}>
    WHERE {{
        ?s a <{class_name}> ;
            <{predicate_name}> ?o .
        FILTER (isLiteral(?o)) .
    }}
    GROUP BY (datatype(?o) AS ?range)
    ORDER BY DESC(COUNT(?range))
    LIMIT 1
    """

    RANGE_CLASS_QUERY = """
    SELECT ?range
    FROM <{graph}>
    WHERE {{
        ?s a <{class_name}> ;
            <{predicate_name}> ?o .
        ?o a ?range .
        FILTER (?range NOT IN (<http://www.w3.org/2002/07/owl#Thing>)) .
    }}
    GROUP BY ?range
    ORDER BY DESC(COUNT(?range))
    LIMIT {limit}
    """

    def __init__(self, endpoint_url: str, graph: str, limit_queries: dict[str, float], max_workers: int):
        """
        Fetch class and predicate information from the SPARQL endpoint.
        Args:
            endpoint_url (str): The URL of the SPARQL endpoint to connect to.
            graph (str): The graph URI to query within the endpoint.
            limit_queries (dict[str, float]): A dictionary specifying query limits.
            max_workers (int): The maximum number of worker threads to use for concurrent operations.
        Funtions:
            get_information(): Returns information about classes and predicates retrieved from the endpoint.
        """
        
        self._endpoint_url = endpoint_url
        self._graph = graph
        self._limit_queries = limit_queries
        self._max_workers = max_workers

    def get_information(self) -> pd.DataFrame:
        # Fetch class information
        logger.info(f'Fetching class information from {self._endpoint_url}...')
        classes = query_sparql(self.CLASS_QUERY.format(graph=self._graph), endpoint_url=self._endpoint_url)['results']['bindings']
        classes = pd.DataFrame(classes).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
        classes['name'] = classes['class'].apply(lambda c: re.sub(r'(?<!^)(?=[A-Z])', ' ', c.split('/')[-1].split('#')[-1]))

        # Filter classes based on frequency
        num_classes = len(classes)
        count_threshold = classes['count'].quantile(self._limit_queries['top_classes_percentile'])
        classes = classes[classes['count'] >= count_threshold].sort_values(by='count', ascending=False).reset_index(drop=True)
        logger.info(f'Keeping {len(classes)}/{num_classes} most frequent classes.')

        # Fetch predicate information
        logger.info(f'Fetching predicate information from {self._endpoint_url}...')
        classes['predicates'] = Parallel(n_jobs=self._max_workers)(
            delayed(self._retrieve_predicates_information)(class_name=c) for c in tqdm(classes['class'].tolist(), total=len(classes))
        )
        return classes

    def _retrieve_predicates_information(self, class_name: str) -> dict[str, str]:
        """Fetch predicates and their ranges for a given class"""

        # Fetch top n predicates
        predicates = query_sparql(
            self.PREDICATE_QUERY.format(
                graph=self._graph,
                class_name=class_name,
                limit=self._limit_queries['top_n_predicates']
            ),
            endpoint_url=self._endpoint_url
        )['results']['bindings']
        predicates = pd.DataFrame(predicates).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))

        # Fetch datatype ranges for each predicate
        predicates['range'] = predicates['predicate'].apply(
            lambda p: (query_sparql(
                self.RANGE_DATATYPE_QUERY.format(
                    graph=self._graph,
                    class_name=class_name,
                    predicate_name=p
                ),
                endpoint_url=self._endpoint_url
            )['results']['bindings'] or [{}])[0]
        ).apply(lambda r: r['range']['value'] if 'range' in r.keys() else pd.NA)

        # Fetch top n class ranges for the remaining predicates
        predicates.loc[predicates['range'].isna(), 'range'] = predicates[predicates['range'].isna()]['predicate'].apply(
            lambda p: (query_sparql(
                self.RANGE_CLASS_QUERY.format(
                    graph=self._graph,
                    class_name=class_name,
                    predicate_name=p,
                    limit=self._limit_queries['top_n_range_classes']
                ),
                endpoint_url=self._endpoint_url
            )['results']['bindings'] or [{}])
        ).apply(lambda l: [r['range']['value'] for r in l] if l != [{}] else pd.NA)
        
        # Fill the remaining predicate ranges
        predicates.loc[predicates['range'].isna(), 'range'] = ''

        return predicates.set_index('predicate')['range'].to_dict()

if __name__ == "__main__":
    start_time = time.time()
    classes = EndpointSchema(
        endpoint_url='http://localhost:8890/sparql/',
        graph='https://text2sparql.aksw.org/2025/corporate/',
        limit_queries={
            'top_classes_percentile': .90,
            'top_n_predicates': 20,
            'top_n_range_classes': 5,
        },
        max_workers=4
    ).get_information()
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time / 60:.2f} minutes")