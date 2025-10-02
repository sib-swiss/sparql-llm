import os
import time

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

"""
Hyperparameter Analysis of SPARQL-LLM
"""

file_time_prefix = time.strftime("%Y%m%d_%H%M")
bench_folder = os.path.join("data", "benchmarks")
os.makedirs(bench_folder, exist_ok=True)
SAVE_PLOTS = False


def plot_proportion_tuning_results(results: pd.DataFrame) -> None:
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)
    plt.figure(figsize=(20, 10))

    ax = sns.lineplot(
        data=results,
        x="proportion",
        y="F1 Score",
        hue="dataset",
        linewidth=3,
        palette=sns.color_palette("Blues")[1::3],
    )

    ax.set_xlabel("Proportion of DBpedia Schema")
    ax.set_ylabel("F1 Score")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.4, 0.7)
    ax.legend_.set_title("TEXT2SPARQL Corpus")
    ax.legend_.set_bbox_to_anchor((1, 1))
    ax.set_xticks([0.05, 0.10, 0.20, 0.50, 0.95], ["5%", "10%", "20%", "50%", "95%"])
    ax.set_yticks([0.2, 0.3, 0.4, 0.5, 0.6, 0.7], [".2", ".3", ".4", ".5", ".6", ".7"])
    sns.despine(top=True, right=True)

    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_proportion_tuning.png"), bbox_inches="tight")
    else:
        plt.show()


def plot_examples_tuning_results(results: pd.DataFrame) -> None:
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=2.5)
    plt.figure(figsize=(20, 10))

    ax = sns.lineplot(
        data=results,
        x="examples",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate", "Overall"],
        linewidth=3,
        palette=sns.color_palette("Blues")[1:5:3]
        + sns.color_palette("Oranges")[1:2]
        + sns.color_palette("Greens")[1:2],
    )

    ax.set_xlabel("Number of Provided Examples")
    ax.set_ylabel("F1 Score")
    ax.set_xlim(0, 21)
    ax.set_ylim(0.2, 0.7)
    ax.legend_.set_title("TEXT2SPARQL Corpus")
    ax.legend_.set_bbox_to_anchor((1, 1))
    ax.set_xticks([1, 5, 10, 20], ["1", "5", "10", "20"])
    ax.set_yticks([0.2, 0.3, 0.4, 0.5, 0.6, 0.7], [".2", ".3", ".4", ".5", ".6", ".7"])
    sns.despine(top=True, right=True)

    if SAVE_PLOTS:
        plt.savefig(os.path.join(bench_folder, f"{file_time_prefix}_examples_tuning.png"), bbox_inches="tight")
    else:
        plt.show()


if __name__ == "__main__":
    # Results from dbpedia proportion tuning
    results = pd.DataFrame(
        [
            {"proportion": 0.05, "dataset": "DBpedia (EN)", "F1 Score": 0.62},
            {"proportion": 0.10, "dataset": "DBpedia (EN)", "F1 Score": 0.68},
            {"proportion": 0.20, "dataset": "DBpedia (EN)", "F1 Score": 0.61},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.63},
            {"proportion": 0.95, "dataset": "DBpedia (EN)", "F1 Score": 0.66},
            {"proportion": 0.05, "dataset": "DBpedia (ES)", "F1 Score": 0.56},
            {"proportion": 0.10, "dataset": "DBpedia (ES)", "F1 Score": 0.64},
            {"proportion": 0.20, "dataset": "DBpedia (ES)", "F1 Score": 0.58},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.60},
            {"proportion": 0.95, "dataset": "DBpedia (ES)", "F1 Score": 0.57},
        ]
    )
    plot_proportion_tuning_results(results)

    # Results from examples tuning
    results = pd.DataFrame(
        [
            {"examples": 1, "dataset": "DBpedia (EN)", "F1 Score": 0.50},
            {"examples": 5, "dataset": "DBpedia (EN)", "F1 Score": 0.59},
            {"examples": 10, "dataset": "DBpedia (EN)", "F1 Score": 0.68},
            {"examples": 20, "dataset": "DBpedia (EN)", "F1 Score": 0.63},
            {"examples": 1, "dataset": "DBpedia (ES)", "F1 Score": 0.46},
            {"examples": 5, "dataset": "DBpedia (ES)", "F1 Score": 0.58},
            {"examples": 10, "dataset": "DBpedia (ES)", "F1 Score": 0.64},
            {"examples": 20, "dataset": "DBpedia (ES)", "F1 Score": 0.69},
            {"examples": 1, "dataset": "Corporate", "F1 Score": 0.27},
            {"examples": 5, "dataset": "Corporate", "F1 Score": 0.40},
            {"examples": 10, "dataset": "Corporate", "F1 Score": 0.44},
            {"examples": 20, "dataset": "Corporate", "F1 Score": 0.44},
            {"examples": 1, "dataset": "Overall", "F1 Score": 0.38},
            {"examples": 5, "dataset": "Overall", "F1 Score": 0.49},
            {"examples": 10, "dataset": "Overall", "F1 Score": 0.55},
            {"examples": 20, "dataset": "Overall", "F1 Score": 0.55},
        ]
    )
    plot_examples_tuning_results(results)
