import os
import time

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns

"""
Hyperparameter Analysis of SPARQL-LLM
"""

def plot_hyperparameter_tuning_results(proportion_results: pd.DataFrame, examples_results: pd.DataFrame, save_plot: bool = False) -> None:
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=3.5)
    _, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10), sharey=True)

    # First subplot - proportion tuning
    sns.lineplot(
        data=proportion_results,
        x="proportion",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate", "Overall"],
        linewidth=5,
        palette=sns.color_palette("Blues")[1:5:3] + sns.color_palette("Oranges")[1:2] + sns.color_palette("Greens")[1:2],
        ax=ax1,
    )

    ax1.set_xlabel("Proportion of Provided Schema")
    ax1.set_ylabel("F1 Score")
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0.1, 0.7)
    ax1.get_legend().remove()
    ax1.set_xticks([0.0, 0.5, 1.0], ["0%", "50%", "100%"])
    ax1.set_yticks([.2, .3, .4, .5, .6, .7], [".2", ".3", ".4", ".5", ".6", ".7"])

    # Second subplot - examples tuning
    sns.lineplot(
        data=examples_results,
        x="examples",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate", "Overall"],
        linewidth=5,
        palette=sns.color_palette("Blues")[1:5:3] + sns.color_palette("Oranges")[1:2] + sns.color_palette("Greens")[1:2],
        ax=ax2,
    )

    ax2.set_xlabel("Number of Provided Examples")
    ax2.set_xlim(0, 21)
    ax2.legend_.set_title("TEXT2SPARQL Corpus")
    ax2.legend_.set_bbox_to_anchor((1, 1))
    ax2.set_xticks([0, 10, 20], ["0", "10", "20"])

    sns.despine(top=True, right=True)

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_hyperparameter_tuning.png"), bbox_inches="tight")
    else:
        plt.show()


if __name__ == "__main__":
    proportion_results = pd.DataFrame(
        [
            # {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": },
            # {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": },
            # {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": },
            {"proportion": 0.10, "dataset": "DBpedia (EN)", "F1 Score": 0.5177818642677522},
            {"proportion": 0.10, "dataset": "DBpedia (EN)", "F1 Score": 0.5315289713061103},
            {"proportion": 0.10, "dataset": "DBpedia (EN)", "F1 Score": 0.5171853349263068},
            {"proportion": 0.20, "dataset": "DBpedia (EN)", "F1 Score": 0.5874967190140884},
            {"proportion": 0.20, "dataset": "DBpedia (EN)", "F1 Score": 0.5786879881257998},
            {"proportion": 0.20, "dataset": "DBpedia (EN)", "F1 Score": 0.5442170061900802},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.6249156554756955},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.5647916605980592},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.5617943435850233},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5570257999788799},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5626547452618874},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5676321864962138},

            # {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": },
            # {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": },
            # {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": },
            {"proportion": 0.10, "dataset": "DBpedia (ES)", "F1 Score": 0.4667763109596714},
            {"proportion": 0.10, "dataset": "DBpedia (ES)", "F1 Score": 0.4677388738349151},
            {"proportion": 0.10, "dataset": "DBpedia (ES)", "F1 Score": 0.4770042256350722},
            {"proportion": 0.20, "dataset": "DBpedia (ES)", "F1 Score": 0.4709356344926672},
            {"proportion": 0.20, "dataset": "DBpedia (ES)", "F1 Score": 0.47393503449746754},
            {"proportion": 0.20, "dataset": "DBpedia (ES)", "F1 Score": 0.45786748886563167},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.4272150033867241},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.45629056532984175},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.4870455208203278},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.45023871583225045},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.4399706216187276},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.4239424397423014},

            # {"proportion": 0.00, "dataset": "Corporate", "F1 Score": },
            # {"proportion": 0.00, "dataset": "Corporate", "F1 Score": },
            # {"proportion": 0.00, "dataset": "Corporate", "F1 Score": },
            {"proportion": 0.10, "dataset": "Corporate", "F1 Score": 0.18119046638740882},
            {"proportion": 0.10, "dataset": "Corporate", "F1 Score": 0.2344946680680811},
            {"proportion": 0.10, "dataset": "Corporate", "F1 Score": 0.18705899555346123},
            {"proportion": 0.20, "dataset": "Corporate", "F1 Score": 0.19461938483737992},
            {"proportion": 0.20, "dataset": "Corporate", "F1 Score": 0.1820129285871166},
            {"proportion": 0.20, "dataset": "Corporate", "F1 Score": 0.18895475679202206},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.24795698419057718},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.2831563128703653},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.3097776133603328},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.3015879005635923},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.3480555354382549},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.2935839848627154},
        ]
    )
    # Calculate overall results as the mean of DBpedia (EN) and DBpedia (ES) and Corporate
    overall_results = proportion_results[proportion_results['dataset'] == 'DBpedia (EN)'].copy()
    overall_results.loc[:, 'dataset'] = 'Overall'
    overall_f1_scores = np.array(
                            [   np.array(
                                    [proportion_results[proportion_results['dataset'] == 'DBpedia (EN)']['F1 Score'].values,
                                    proportion_results[proportion_results['dataset'] == 'DBpedia (ES)']['F1 Score'].values]
                                ).mean(axis=0),
                                proportion_results[proportion_results['dataset'] == 'Corporate']['F1 Score'].values
                            ]
                        ).mean(axis=0)
    overall_results.loc[:, 'F1 Score'] = overall_f1_scores
    proportion_results = pd.concat([proportion_results, overall_results], axis=0).reset_index(drop=True)

    examples_results = pd.DataFrame(
        [
            # {"examples": 0, "dataset": "DBpedia (EN)", "F1 Score": },
            # {"examples": 0, "dataset": "DBpedia (EN)", "F1 Score": },
            # {"examples": 0, "dataset": "DBpedia (EN)", "F1 Score": },
            {"examples": 1, "dataset": "DBpedia (EN)", "F1 Score": 0.50},
            {"examples": 5, "dataset": "DBpedia (EN)", "F1 Score": 0.59},
            {"examples": 10, "dataset": "DBpedia (EN)", "F1 Score": 0.68},
            {"examples": 20, "dataset": "DBpedia (EN)", "F1 Score": 0.63},

            # {"examples": 0, "dataset": "DBpedia (ES)", "F1 Score": },
            # {"examples": 0, "dataset": "DBpedia (ES)", "F1 Score": },
            # {"examples": 0, "dataset": "DBpedia (ES)", "F1 Score": },
            {"examples": 1, "dataset": "DBpedia (ES)", "F1 Score": 0.46},
            {"examples": 5, "dataset": "DBpedia (ES)", "F1 Score": 0.58},
            {"examples": 10, "dataset": "DBpedia (ES)", "F1 Score": 0.64},
            {"examples": 20, "dataset": "DBpedia (ES)", "F1 Score": 0.69},

            # {"examples": 0, "dataset": "Corporate", "F1 Score": },
            # {"examples": 0, "dataset": "Corporate", "F1 Score": },
            # {"examples": 0, "dataset": "Corporate", "F1 Score": },
            {"examples": 1, "dataset": "Corporate", "F1 Score": 0.27},
            {"examples": 5, "dataset": "Corporate", "F1 Score": 0.40},
            {"examples": 10, "dataset": "Corporate", "F1 Score": 0.44},
            {"examples": 20, "dataset": "Corporate", "F1 Score": 0.44},
        ]
    )
    # Calculate overall results as the mean of DBpedia (EN) and DBpedia (ES) and Corporate
    overall_results = examples_results[examples_results['dataset'] == 'DBpedia (EN)'].copy()
    overall_results.loc[:, 'dataset'] = 'Overall'
    overall_f1_scores = np.array(
                            [   np.array(
                                    [examples_results[examples_results['dataset'] == 'DBpedia (EN)']['F1 Score'].values,
                                    examples_results[examples_results['dataset'] == 'DBpedia (ES)']['F1 Score'].values]
                                ).mean(axis=0),
                                examples_results[examples_results['dataset'] == 'Corporate']['F1 Score'].values
                            ]
                        ).mean(axis=0)
    overall_results.loc[:, 'F1 Score'] = overall_f1_scores
    examples_results = pd.concat([examples_results, overall_results], axis=0).reset_index(drop=True)

    plot_hyperparameter_tuning_results(proportion_results=proportion_results,
                                       examples_results=examples_results,
                                       save_plot=False,
                                    )