import logging
import os
import re
import pandas as pd
from sparql_llm.utils import EndpointsSchemaDict, SchemaDict, query_sparql
import time
from joblib import Parallel, delayed
from tqdm import tqdm
import json

logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)

class EndpointSchema:
    _CLASS_QUERY = """
    SELECT ?class (COUNT(?class) AS ?count)
    FROM <{graph}>
    WHERE {{
        ?s a ?class .
    }}
    GROUP BY ?class
    """

    _PREDICATE_QUERY = """
    SELECT ?predicate
    FROM <{graph}>
    WHERE {{
        ?s a <{class_name}> ;
            ?predicate ?o .
    }}
    GROUP BY ?predicate
    ORDER BY DESC(COUNT(?predicate))
    LIMIT {limit}
    """

    _RANGE_QUERY = """
    SELECT ?range
    FROM <{graph}>
    WHERE {{
        ?s a <{class_name}> ;
            <{predicate_name}> ?o .
        OPTIONAL {{
            FILTER(isIRI(?o))
            ?o a ?class .
        }}

        BIND (IF(BOUND(?class), ?class, DATATYPE(?o)) AS ?range)
    }}
    GROUP BY ?range
    ORDER BY DESC(COUNT(?range))
    LIMIT {limit}
    """

    _EXCLUDE_CLASS_PATTERN = re.compile(r'^http://www\.w3\.org/2002/07/owl#Thing$|ontologydesignpatterns\.org')

    def __init__(self, endpoint_url: str, graph: str, limit_queries: dict[str, float], max_workers: int, force_recompute: bool, schema_path: str) -> None:
        """
        Fetch class and predicate information from the SPARQL endpoint.
        Args:
            endpoint_url (str): The URL of the SPARQL endpoint to connect to.
            graph (str): The graph URI to query within the endpoint.
            limit_queries (dict[str, float]): A dictionary specifying query limits.
            max_workers (int): The maximum number of worker threads to use for concurrent operations.
        Funtions:
            get_schema(path: str): Returns information about classes and predicates retrieved from the endpoint.
        """
        
        self._endpoint_url = endpoint_url
        self._graph = graph
        self._limit_queries = limit_queries
        self._max_workers = max_workers
        self._force_recompute = force_recompute
        self._schema_path = schema_path

    def get_schema(self) -> pd.DataFrame:
        """Load schema information from a JSON file."""

        if not os.path.exists(self._schema_path) or self._force_recompute:
            self._save_schema_dict()

        with open(self._schema_path, 'r', encoding='utf-8') as f:
            schema = pd.DataFrame([{'class':key, 'predicates':value} for key, value in json.load(f)[self._endpoint_url].items()])

        # Add a human-readable name for each class
        schema['name'] = schema['class'].apply(lambda c: re.sub(r'(?<!^)(?=[A-Z])', ' ', c.split('/')[-1].split('#')[-1]))

        return schema
    
    def _save_schema_dict(self) -> None:
        """Fetch class and predicate information from the SPARQL endpoint and save to JSON file."""
        # Fetch class information
        logger.info(f'Fetching class information from {self._endpoint_url}...')
        schema = query_sparql(self._CLASS_QUERY.format(graph=self._graph), endpoint_url=self._endpoint_url)['results']['bindings']
        schema = pd.DataFrame(schema).map(lambda x: x['value']).assign(count=lambda df: df['count'].astype(int))
        
        # Exclude unwanted classes
        schema = schema[schema['class'].apply(lambda c: not bool(re.search(self._EXCLUDE_CLASS_PATTERN, c)))]

        # Filter classes based on frequency
        num_classes = len(schema)
        count_threshold = schema['count'].quantile(self._limit_queries['top_classes_percentile'])
        schema = schema[schema['count'] >= count_threshold].sort_values(by='count', ascending=False).reset_index(drop=True)
        logger.info(f'Keeping {len(schema)}/{num_classes} most frequent classes.')

        # Fetch predicate information
        logger.info(f'Fetching predicate information from {self._endpoint_url}...')
        schema['predicates'] = Parallel(n_jobs=self._max_workers)(
            delayed(self._retrieve_class_information)(class_name=c) for c in tqdm(schema['class'].tolist(), total=len(schema))
        )

        schema_dict = SchemaDict({i['class']:i['predicates'] for i in schema.to_dict(orient='records')})
        endpoint_schema_dict = EndpointsSchemaDict({self._endpoint_url:schema_dict})
        with open(self._schema_path, 'w') as f:
            json.dump(endpoint_schema_dict, f, indent=2)

    def _retrieve_class_information(self, class_name: str) -> dict[str, list[str]]:
        """Fetch predicates and their ranges for a given class"""

        # Fetch top n predicates
        predicates = query_sparql(
            self._PREDICATE_QUERY.format(
                graph=self._graph,
                class_name=class_name,
                limit=self._limit_queries['top_n_predicates']
            ),
            endpoint_url=self._endpoint_url
        )['results']['bindings'] or []
        predicates = pd.DataFrame(predicates)[['predicate']].map(lambda p: p['value'] if 'value' in p else pd.NA).dropna()

        # Fetch top n ranges for the predicates
        predicates['range'] = predicates['predicate'].apply(lambda p: (self._retrieve_predicate_information(class_name, p)))

        return predicates.set_index('predicate')['range'].to_dict()

    def _retrieve_predicate_information(self, class_name: str, predicate_name: str) -> list[str]:
        """Fetch ranges for a given predicate of a class"""

        range = query_sparql(
            self._RANGE_QUERY.format(
                graph=self._graph,
                class_name=class_name,
                predicate_name=predicate_name,
                limit=self._limit_queries['top_n_ranges']
            ),
            endpoint_url=self._endpoint_url
        )['results']['bindings'] or []

        # Filter out unwanted ranges
        range = [r['range']['value'] for r in range if (('range' in r) and ('value' in r['range']) and (not bool(re.search(self._EXCLUDE_CLASS_PATTERN, r['range']['value']))))]

        return range


if __name__ == "__main__":
    start_time = time.time()
    schema = EndpointSchema(
        endpoint_url='http://localhost:8890/sparql/',
        graph='https://text2sparql.aksw.org/2025/corporate/',
        limit_queries={
            'top_classes_percentile': 0,
            'top_n_predicates': 20,
            'top_n_ranges': 1,
        },
        max_workers=4,
        force_recompute=True,
        schema_path=os.path.join('data', 'benchmarks', 'Text2SPARQL', 'schemas', 'corporate_schema.json'),
    )
    
    schema = EndpointSchema(
        endpoint_url='http://localhost:8890/sparql/',
        graph='https://text2sparql.aksw.org/2025/dbpedia/',
        limit_queries={
            'top_classes_percentile': .90,
            'top_n_predicates': 20,
            'top_n_ranges': 1,
        },
        max_workers=4,
        force_recompute=True,
        schema_path=os.path.join('data', 'benchmarks', 'Text2SPARQL', 'schemas', 'dbpedia_schema.json'),
    )
    
    # Debugging examples
    # schema._save_schema_dict()
    # schema = schema._retrieve_class_information(class_name='http://ld.company.org/prod-vocab/Supplier')
    # schema = schema._retrieve_predicate_information(class_name='http://ld.company.org/prod-vocab/Supplier', predicate_name='http://ld.company.org/prod-vocab/country')
    # schema = schema._retrieve_predicate_information(class_name='http://dbpedia.org/ontology/City', predicate_name='http://dbpedia.org/property/longd')
    # schema = schema.get_information()
    # logger.info(f"Schema information: {schema}")
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time / 60:.2f} minutes")