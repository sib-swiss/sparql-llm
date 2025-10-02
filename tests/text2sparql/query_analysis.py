import os
import time

import matplotlib.pyplot as plt
import pandas as pd
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
    queries["triple patterns"] = queries["triple patterns"].apply(lambda x: 6 if x > 6 else x)
    queries["dataset"] = queries["dataset"].map(
        lambda d: {
            "Generated-CK": "LLM-Generated (Corporate)",
            "Text2SPARQL-db": "TEXT2SPARQL (DBpedia)",
            "Text2SPARQL-ck": "TEXT2SPARQL (Corporate)",
            "LC-QuAD": "LC-QuAD (DBpedia)",
            "QALD-9+": "QALD-9+ (DBpedia)",
        }.get(d, d)
    )
    queries = queries.groupby(["dataset", "triple patterns"]).size().reset_index(name="count")

    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)

    ax = sns.lineplot(
        data=queries,
        x="triple patterns",
        y="count",
        hue="dataset",
        hue_order=[
            "LC-QuAD (DBpedia)",
            "QALD-9+ (DBpedia)",
            "TEXT2SPARQL (DBpedia)",
            "LLM-Generated (Corporate)",
            "TEXT2SPARQL (Corporate)",
        ],
        linewidth=3,
        palette=sns.color_palette("Blues")[1::2] + sns.color_palette("Oranges")[1:4:2],
    )

    ax.lines[2].set_linestyle("dashed")
    ax.lines[4].set_linestyle("dashed")
    ax.set_xlabel("Triple Patterns")
    ax.set_ylabel("Queries")
    ax.set_yscale("log")
    ax.set_ylim(0.5, 10000)
    ax.legend_.set_title("KGQA Corpus")
    ax.legend_.get_lines()[2].set_linestyle("dashed")
    ax.legend_.get_lines()[4].set_linestyle("dashed")
    ax.legend_.set_bbox_to_anchor((1, 1))
    ax.set_xticks([1, 2, 3, 4, 5, 6], ["1", "2", "3", "4", "5", "[6-8]"])
    sns.despine(top=True, right=True)

    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_triple_patterns.png"), bbox_inches="tight")
    else:
        plt.show()


def print_error_histogram():
    # Custom error analysis using a manually annotated file
    csv_file = os.path.join("data", "benchmarks", "20250624_1346_Text2SPARQL_Error_Analysis.csv")
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        error_counts = df["comment"].str.split("/").explode().str.strip().value_counts()
        print(error_counts)


if __name__ == "__main__":
    queries = pd.read_csv(QUERIES_FILE)
    plot_queries_by_dataset(queries)
    plot_result_length(queries)
    plot_triple_patterns(queries)
    print_error_histogram()
