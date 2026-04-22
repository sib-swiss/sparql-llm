import os
import time
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytrec_eval
import seaborn as sns

"""
Quantitative and Qualitative Analysis of Benchmark Queries
"""

QUERIES_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "queries.csv")
file_time_prefix = time.strftime("%Y%m%d_%H%M")
bench_folder = os.path.join("data", "benchmarks")
os.makedirs(bench_folder, exist_ok=True)
SAVE_PLOTS = False


def plot_queries_by_dataset(queries: pd.DataFrame):
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)
    plt.figure(figsize=(20, 10))
    ax = sns.countplot(
        data=queries,
        y="dataset",
        hue="query type",
        order=queries["dataset"].value_counts().index[::-1],
        palette=sns.color_palette("tab10")[: -(len(queries["query type"].unique()) + 1) : -1],
    )
    ax.set_xlabel("Queries")
    ax.set_ylabel("Dataset")
    ax.set_xscale("log")
    ax.set_xlim(0.5, 10000)
    ax.legend_.set_title("Query Type")
    sns.despine(top=True, right=True)
    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_queries_by_dataset.png"), bbox_inches="tight")
    else:
        plt.show()


def plot_result_length(queries: pd.DataFrame):
    queries["result length"] = queries["result length"].apply(lambda x: 2 if x > 2 else x)
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)
    plt.figure(figsize=(20, 10))
    ax = sns.histplot(
        data=queries,
        x="result length",
        hue="dataset",
        multiple="dodge",
        stat="count",
        shrink=0.8,
        discrete=True,
        palette="tab10",
    )
    ax.set_xlabel("Result Length")
    ax.set_ylabel("Queries")
    ax.set_yscale("log")
    ax.set_ylim(0.5, 10000)
    ax.legend_.set_title("Dataset")
    ax.legend_.set_bbox_to_anchor((1, 1.05))
    ax.set_xticks([0, 1, 2], ["0", "1", "2+"])
    sns.despine(top=True, right=True)
    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_result_length.png"), bbox_inches="tight")
    else:
        plt.show()


def plot_triple_patterns(queries: pd.DataFrame):
    queries = queries.copy()
    queries["dataset"] = queries["dataset"].map(
        lambda d: {
            "Generated-CK": "Corporate (LLM-Generated)",
            "Text2SPARQL-db": "DBpedia (EN) & DBpedia (ES)",
            "Text2SPARQL-ck": "Corporate",
            "LC-QuAD": "LC-QuAD",
            "QALD-9+": "QALD-9+",
        }.get(d, d)
    )

    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)

    ax = sns.kdeplot(
        data=queries,
        x="triple patterns",
        hue="dataset",
        hue_order=[
            "LC-QuAD",
            "QALD-9+",
            "DBpedia (EN) & DBpedia (ES)",
            "Corporate (LLM-Generated)",
            "Corporate",
        ],
        linewidth=3,
        common_norm=False,
        clip=(0, 6),
        palette=sns.color_palette("Blues")[1::2] + sns.color_palette("Oranges")[1:4:2],
    )

    ax.lines[2].set_linestyle("dashed")
    ax.lines[0].set_linestyle("dashed")
    ax.set_xlabel("Triple Patterns")
    ax.legend_.set_title("KGQA Corpus")
    ax.legend_.get_lines()[2].set_linestyle("dashed")
    ax.legend_.get_lines()[4].set_linestyle("dashed")
    ax.legend_.set_bbox_to_anchor((1, 1))
    sns.despine(top=True, right=True)

    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_triple_patterns.png"), bbox_inches="tight")
    else:
        plt.show()


def plot_bio_triple_patterns(queries: pd.DataFrame):
    queries = queries.copy()
    queries["dataset"] = queries.apply(
        lambda q: q["dataset"] + " (Federated)" if q["federated"] else q["dataset"], axis=1
    )

    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)

    ax = sns.kdeplot(
        data=queries,
        x="triple patterns",
        hue="dataset",
        hue_order=[
            "Uniprot",
            "Uniprot (Federated)",
            "Cellosaurus",
            "Cellosaurus (Federated)",
            "Bgee",
            "Bgee (Federated)",
        ],
        linewidth=3,
        common_norm=False,
        clip=(0, 32),
        palette=sns.color_palette("Paired")[:6],
    )

    ax.set_xlabel("Triple Patterns")
    ax.legend_.set_title("BioKGQA Corpus")
    ax.legend_.set_bbox_to_anchor((1, 1))
    sns.despine(top=True, right=True)

    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_bio_triple_patterns.png"), bbox_inches="tight")
    else:
        plt.show()


def print_error_histogram():
    # Custom error analysis using a manually annotated file
    csv_file = os.path.join("data", "benchmarks", "20250624_1346_Text2SPARQL_Error_Analysis.csv")
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        error_counts = df["comment"].str.split("/").explode().str.strip().value_counts()
        print(error_counts)

def print_federated_bio_f1_score(queries: pd.DataFrame) -> float:

    def sparql_results_to_trec(question: str, sparql_dict: dict[str, Any]) -> dict[str, Any]:
        """Transform a SPARQL results dict into a dict to be evaluated through the pyTREC library.

        Args:
            sparql_dict (dict): Dictionary of the URIs, returned by the end-point

        Returns:
            dict: Dictionary of the predicted lists in which all items have the same weight
        """
        d: dict[str, Any] = {}
        d[question] = {}
        try:
            if "boolean" in sparql_dict:
                bool_result = sparql_dict["boolean"]
                d[question]["true"] = 1 if bool_result else 0
            else:
                # print(sparql_dict)
                list_results = sparql_dict["results"]["bindings"]
                list_vars = sparql_dict["head"]["vars"]
                # We add all vars found flattened and compare this
                for var in list_vars:
                    for value in list_results:
                        if var in value:
                            d[question][value[var]["value"]] = 1
        except Exception as e:
            print(f"⚠️ Could not transform SPARQL results to TREC format: {e}")
        return d

    def compute_trec_eval(question: str, reference_results: dict[str, Any], generated_results: dict[str, Any]) -> dict[str, Any]:

        reference_results = sparql_results_to_trec(question, reference_results)
        generated_results = sparql_results_to_trec(question, generated_results)

        f1_score = pytrec_eval.RelevanceEvaluator(reference_results, {"set_F"}).evaluate(generated_results)
        f1_score = f1_score[question]["set_F"]
        return f1_score

    for dataset in ["uniprot", "cellosaurus", "bgee"]:
        for model in ["gpt-5", "gpt-4o-mini", "gpt-oss-120b"]:
             for fold in [1, 2, 3]:

                bio_bench_file = os.path.join("data", "benchmarks", "20251126", f"{dataset}_{model}_fold{fold}.jsonl")
                bio_bench = pd.read_json(bio_bench_file, lines=True)

                bio_bench["F1_Score"] = bio_bench.apply(lambda r: compute_trec_eval(r["question"], r["reference_results"], r["generated_results"]), axis=1)
                bio_bench = bio_bench.merge(queries[["question", "federated"]], on="question", how="left")
                bio_bench = bio_bench[bio_bench["federated"]]
                f1_score = bio_bench["F1_Score"].mean()
                print(f"Dataset: {dataset}, Model: {model}, Fold: {fold}, F1 Score: {f1_score}")

if __name__ == "__main__":
    queries = pd.read_csv(QUERIES_FILE)
    print_federated_bio_f1_score(queries)
    plot_queries_by_dataset(queries)
    plot_result_length(queries)
    plot_triple_patterns(queries)
    plot_bio_triple_patterns(queries)
    print_error_histogram()
