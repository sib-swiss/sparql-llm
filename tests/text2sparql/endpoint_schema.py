import json
import logging
import os
import re
import time

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from joblib import Parallel, delayed
from tqdm import tqdm

from sparql_llm.utils import EndpointsSchemaDict, SchemaDict, query_sparql

logger = logging.getLogger("sparql_llm")
logger.setLevel(logging.INFO)


class EndpointSchema:
    _CLASS_PREDICATE_QUERY = """
    SELECT ?class ?predicate COUNT(*) AS ?count
    FROM <{graph}>
    WHERE {{
        ?s a ?class ;
            ?predicate ?o .
    }}
    GROUP BY ?class ?predicate
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
    _EXCLUDE_CLASS_PATTERN = re.compile(r"^http://www\.w3\.org/2002/07/owl#Thing$|ontologydesignpatterns\.org")

    def __init__(
        self,
        endpoint_url: str,
        graph: str,
        limit_schema: dict[str, float],
        max_workers: int,
        force_recompute: bool,
        schema_path: str,
    ) -> None:
        """
        Fetch class and predicate information from the SPARQL endpoint.
        Args:
            endpoint_url (str): The URL of the SPARQL endpoint to connect to.
            graph (str): The graph URI to query within the endpoint.
            limit_queries (dict[str, float]): A dictionary specifying query limits.
            max_workers (int): The maximum number of worker threads to use for concurrent operations.
        Funtions:
            get_schema(): Returns information about classes and predicates retrieved from the endpoint.
            plot_heatmap(apply_limit: bool): Plots heatmap with classes and predicates retrieved from the endpoint.
        """

        self._endpoint_url = endpoint_url
        self._graph = graph
        self._limit_schema = limit_schema
        self._max_workers = max_workers
        self._force_recompute = force_recompute
        self._schema_path = schema_path

    def _save_schema_dict(self) -> None:
        """Fetch class and predicate information from the SPARQL endpoint and save to JSON file."""
        # Fetch counts information
        logger.info(f"Fetching class-predicate frequency information from {self._endpoint_url}...")
        schema = query_sparql(
            self._CLASS_PREDICATE_QUERY.format(graph=self._graph),
            endpoint_url=self._endpoint_url,
            check_service_desc=False,
        )["results"]["bindings"]
        schema = pd.DataFrame(schema).map(lambda x: x["value"]).assign(count=lambda df: df["count"].astype(int))
        schema = schema.sort_values(by="count", ascending=False)

        # Exclude unwanted classes
        num_classes = len(schema["class"].unique())
        schema = schema[schema["class"].apply(lambda c: not bool(re.search(self._EXCLUDE_CLASS_PATTERN, c)))]

        # Transform to wide format
        schema_wide = schema.pivot_table(index="class", columns="predicate", values="count", fill_value=0)
        schema_wide = schema_wide.reindex(index=schema["class"].unique(), columns=schema["predicate"].unique())

        # Apply limits to the number of classes and predicates
        schema_wide = schema_wide.iloc[
            : int((1 - self._limit_schema["top_classes_percentile"]) * len(schema_wide.index)),
            : int((1 - self._limit_schema["top_classes_percentile"]) * len(schema_wide.columns)),
        ]

        # Transform back to long format
        schema = schema_wide.reset_index().melt(id_vars="class", var_name="predicate", value_name="count")
        schema = schema[schema["count"] > 0].reset_index(drop=True)
        logger.info(f"Keeping {len(schema['class'].unique())}/{num_classes} most frequent classes.")

        # keep top predicates for each class
        schema = (
            schema.groupby("class")[["predicate", "count"]]
            .apply(lambda df: df.nlargest(self._limit_schema["top_n_predicates"], "count"))
            .reset_index()
        )

        # Fetch range information
        logger.info(f"Fetching range information from {self._endpoint_url}...")
        schema["range"] = Parallel(n_jobs=self._max_workers)(
            delayed(self._retrieve_predicate_information)(class_name=c, predicate_name=p)
            for _, (c, p) in tqdm(schema[["class", "predicate"]].iterrows(), total=len(schema))
        )
        # schema = schema[schema['range'].apply(lambda r: len(r) > 0)]
        schema = (
            schema.groupby("class")[["predicate", "range"]]
            .apply(lambda df: df.set_index("predicate")["range"].to_dict())
            .reset_index()
            .rename(columns={0: "predicates"})
        )

        # Save schema to JSON file
        logger.info(f"Saving schema information from {self._endpoint_url}...")
        schema_dict = SchemaDict({i["class"]: i["predicates"] for i in schema.to_dict(orient="records")})
        endpoint_schema_dict = EndpointsSchemaDict({self._endpoint_url: schema_dict})
        with open(self._schema_path, "w") as f:
            json.dump(endpoint_schema_dict, f, indent=2)

    def _retrieve_predicate_information(self, class_name: str, predicate_name: str) -> list[str]:
        """Fetch ranges for a given predicate of a class"""
        try:
            range = (
                query_sparql(
                    self._RANGE_QUERY.format(
                        graph=self._graph,
                        class_name=class_name,
                        predicate_name=predicate_name,
                        limit=self._limit_schema["top_n_ranges"],
                        check_service_desc=False,
                    ),
                    endpoint_url=self._endpoint_url,
                )["results"]["bindings"]
                or []
            )

            # Filter out unwanted ranges
            range = [
                r["range"]["value"]
                for r in range
                if (
                    ("range" in r)
                    and ("value" in r["range"])
                    and (not bool(re.search(self._EXCLUDE_CLASS_PATTERN, r["range"]["value"])))
                )
            ]
        except Exception as e:
            logger.warning(f"Error retrieving range for {class_name} - {predicate_name}: {e}")
            range = []
        return range

    def get_schema(self) -> pd.DataFrame:
        """Load schema information from a JSON file."""

        if not os.path.exists(self._schema_path) or self._force_recompute:
            self._save_schema_dict()

        with open(self._schema_path, encoding="utf-8") as f:
            schema = pd.DataFrame(
                [{"class": key, "predicates": value} for key, value in json.load(f)[self._endpoint_url].items()]
            )

        # Add a human-readable name for each class
        schema["name"] = schema["class"].apply(
            lambda c: re.sub(r"(?<!^)(?=[A-Z])", " ", c.split("/")[-1].split("#")[-1])
        )

        return schema

    def plot_heatmap(self, apply_limit: bool = True) -> None:
        # Fetch counts information
        logger.info(f"Fetching counts information from {self._endpoint_url}...")
        counts = query_sparql(self._CLASS_PREDICATE_QUERY.format(graph=self._graph), endpoint_url=self._endpoint_url)[
            "results"
        ]["bindings"]
        counts = pd.DataFrame(counts).map(lambda x: x["value"]).assign(count=lambda df: df["count"].astype(int))
        counts = counts.sort_values(by="count", ascending=False)

        # Exclude unwanted classes
        counts = counts[counts["class"].apply(lambda c: not bool(re.search(self._EXCLUDE_CLASS_PATTERN, c)))]

        # Transform counts DataFrame to have class-predicate matrix format
        heatmap = counts.pivot_table(index="class", columns="predicate", values="count", fill_value=0)
        heatmap = heatmap.reindex(index=counts["class"].unique(), columns=counts["predicate"].unique())

        # Apply limits to the number of classes and predicates
        if apply_limit:
            heatmap = heatmap.iloc[
                : int((1 - self._limit_schema["top_classes_percentile"]) * len(heatmap.index)),
                : int((1 - self._limit_schema["top_classes_percentile"]) * len(heatmap.columns)),
            ]

        # Plot heatmap
        sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)
        plt.figure(figsize=(20, 10))
        ax = sns.heatmap(heatmap, mask=(heatmap == 0), cmap="rocket_r", cbar=True, robust=True)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel("Predicates")
        ax.set_ylabel("Classes")
        ax.set_title(
            f"{self._schema_path.split('/')[-1].split('_')[0].capitalize()} Co-Occurrence Heatmap", fontsize=20
        )
        sns.despine(top=True, right=True)
        plt.savefig(f"{self._schema_path.split('.')[0] + ('' if apply_limit else '_full')}.png", bbox_inches="tight")


if __name__ == "__main__":
    start_time = time.time()
    schema = EndpointSchema(
        endpoint_url="http://localhost:8890/sparql/",
        graph="https://text2sparql.aksw.org/2025/corporate/",
        limit_schema={
            "top_classes_percentile": 0,
            "top_n_predicates": 20,
            "top_n_ranges": 1,
        },
        max_workers=4,
        force_recompute=True,
        schema_path=os.path.join("data", "benchmarks", "Text2SPARQL", "schemas", "corporate_schema.json"),
    )

    schema = EndpointSchema(
        endpoint_url="http://localhost:8890/sparql/",
        graph="https://text2sparql.aksw.org/2025/dbpedia/",
        limit_schema={
            "top_classes_percentile": 0.90,
            "top_n_predicates": 20,
            "top_n_ranges": 1,
        },
        max_workers=4,
        force_recompute=True,
        schema_path=os.path.join("data", "benchmarks", "Text2SPARQL", "schemas", "dbpedia_schema.json"),
    )

    # Debugging examples
    # schema.plot_heatmap()
    # schema._save_schema_dict()
    # schema = schema._retrieve_class_information(class_name='http://ld.company.org/prod-vocab/Supplier')
    # schema = schema._retrieve_predicate_information(class_name='http://ld.company.org/prod-vocab/Supplier', predicate_name='http://ld.company.org/prod-vocab/country')
    # schema = schema._retrieve_predicate_information(class_name='http://dbpedia.org/ontology/City', predicate_name='http://dbpedia.org/property/longd')
    # schema = schema.get_information()
    # logger.info(f"Schema information: {schema}")
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time / 60:.2f} minutes")
