import os
import time

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns

"""
Hyperparameter Analysis of SPARQL-LLM
"""

def plot_hyperparameter_tuning_results(proportion_results: pd.DataFrame, embeddings_results: pd.DataFrame, examples_results: pd.DataFrame, save_plot: bool = False) -> None:
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=5.5)
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(50, 10), sharey=True)
    plt.subplots_adjust(wspace=.1)

    # First subplot - proportion tuning
    sns.lineplot(
        data=proportion_results,
        x="proportion",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        linewidth=5,
        palette=sns.color_palette("Blues")[1:5:3] + sns.color_palette("Oranges")[1:2],
        ax=ax1,
    )

    ax1.set_xlabel("Proportion of Provided Schema")
    ax1.set_ylabel("F1 Score")
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0.1, 0.7)
    ax1.get_legend().remove()
    ax1.set_xticks([.0, .25, .5, .75, 1.0], ["0%", '25%', "50%", '75%', "100%"])
    ax1.set_yticks([.2, .3, .4, .5, .6, .7], [".2", ".3", ".4", ".5", ".6", ".7"])

    # Second subplot - embeddings tuning
    sns.barplot(
        data=embeddings_results,
        x="embeddings",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        palette=sns.color_palette("Blues")[1:5:3] + sns.color_palette("Oranges")[1:2],
        ax=ax2,
    )

    ax2.set_xlabel("Embeddings Model")
    ax2.get_legend().remove()

    # Third subplot - examples tuning
    sns.lineplot(
        data=examples_results,
        x="examples",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        linewidth=5,
        palette=sns.color_palette("Blues")[1:5:3] + sns.color_palette("Oranges")[1:2],
        ax=ax3,
    )

    ax3.set_xlabel("Number of Provided Examples")
    ax3.set_xlim(0, 20)
    ax3.get_legend().remove()
    ax3.set_xticks([0, 5, 10, 15, 20], ["0", "5", "10", "15", "20"])

    fig.legend(*ax2.get_legend_handles_labels(), bbox_to_anchor=(0.5, 1.1), loc='upper center', ncol=4, title="TEXT2SPARQL Corpus")
    sns.despine(top=True, right=True)

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_hyperparameter_tuning.png"), bbox_inches="tight")
    else:
        plt.show()


if __name__ == "__main__":
    proportion_results = pd.DataFrame(
        [
            {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5586293994429258},
            {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5674128215974444},
            {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5577725555069302},
            {"proportion": 0.25, "dataset": "DBpedia (EN)", "F1 Score": 0.5007120278213574},
            {"proportion": 0.25, "dataset": "DBpedia (EN)", "F1 Score": 0.5267660830673997},
            {"proportion": 0.25, "dataset": "DBpedia (EN)", "F1 Score": 0.5346610817243259},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.6249156554756955},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.5647916605980592},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.5617943435850233},
            {"proportion": 0.75, "dataset": "DBpedia (EN)", "F1 Score": 0.610549656229553},
            {"proportion": 0.75, "dataset": "DBpedia (EN)", "F1 Score": 0.5953462769800143},
            {"proportion": 0.75, "dataset": "DBpedia (EN)", "F1 Score": 0.5987760360118075},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5570257999788799},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5626547452618874},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5676321864962138},

            {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": 0.44942354366452286},
            {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": 0.46589599979623997},
            {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": 0.4499721506825501},
            {"proportion": 0.25, "dataset": "DBpedia (ES)", "F1 Score": 0.48322421974123897},
            {"proportion": 0.25, "dataset": "DBpedia (ES)", "F1 Score": 0.4754533381505741},
            {"proportion": 0.25, "dataset": "DBpedia (ES)", "F1 Score": 0.4692675547194026},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.4272150033867241},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.45629056532984175},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.4870455208203278},
            {"proportion": 0.75, "dataset": "DBpedia (ES)", "F1 Score": 0.45821566063040947},
            {"proportion": 0.75, "dataset": "DBpedia (ES)", "F1 Score": 0.4281971067358794},
            {"proportion": 0.75, "dataset": "DBpedia (ES)", "F1 Score": 0.44691214932689816},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.45023871583225045},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.4399706216187276},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.4239424397423014},

            {"proportion": 0.00, "dataset": "Corporate", "F1 Score": 0.19634836112425091},
            {"proportion": 0.00, "dataset": "Corporate", "F1 Score": 0.22619230376571678},
            {"proportion": 0.00, "dataset": "Corporate", "F1 Score": 0.24963302678538718},
            {"proportion": 0.25, "dataset": "Corporate", "F1 Score": 0.1565782833448236},
            {"proportion": 0.25, "dataset": "Corporate", "F1 Score": 0.14550866715155986},
            {"proportion": 0.25, "dataset": "Corporate", "F1 Score": 0.15889616460213127},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.24795698419057718},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.2831563128703653},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.3097776133603328},
            {"proportion": 0.75, "dataset": "Corporate", "F1 Score": 0.2919913094527303},
            {"proportion": 0.75, "dataset": "Corporate", "F1 Score": 0.244902286195286},
            {"proportion": 0.75, "dataset": "Corporate", "F1 Score": 0.29464500250890013},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.3015879005635923},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.3480555354382549},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.2935839848627154},
        ]
    )
    # # Calculate overall results as the mean of DBpedia (EN) and DBpedia (ES) and Corporate
    # overall_results = proportion_results[proportion_results['dataset'] == 'DBpedia (EN)'].copy()
    # overall_results.loc[:, 'dataset'] = 'Overall'
    # overall_f1_scores = np.array([
    #                                 proportion_results[proportion_results['dataset'] == 'DBpedia (EN)']['F1 Score'].values,
    #                                 proportion_results[proportion_results['dataset'] == 'DBpedia (ES)']['F1 Score'].values,
    #                                 proportion_results[proportion_results['dataset'] == 'Corporate']['F1 Score'].values,
    #                             ]
    #                     )
    # overall_f1_scores = np.average(overall_f1_scores, axis=0, weights=[1, 1, 0.5])
    # overall_results.loc[:, 'F1 Score'] = overall_f1_scores
    # proportion_results = pd.concat([proportion_results, overall_results], axis=0).reset_index(drop=True)

    embeddings_results = pd.DataFrame(
        [
            {"embeddings": r'$baai_S$', "dataset": "DBpedia (EN)", "F1 Score": 0.610549656229553},
            {"embeddings": r'$baai_S$', "dataset": "DBpedia (EN)", "F1 Score": 0.5953462769800143},
            {"embeddings": r'$baai_S$', "dataset": "DBpedia (EN)", "F1 Score": 0.5987760360118075},

            {"embeddings": r'$baai_S$', "dataset": "DBpedia (ES)", "F1 Score": 0.45821566063040947},
            {"embeddings": r'$baai_S$', "dataset": "DBpedia (ES)", "F1 Score": 0.4281971067358794},
            {"embeddings": r'$baai_S$', "dataset": "DBpedia (ES)", "F1 Score": 0.44691214932689816},

            {"embeddings": r'$baai_S$', "dataset": "Corporate", "F1 Score": 0.3015879005635923},
            {"embeddings": r'$baai_S$', "dataset": "Corporate", "F1 Score": 0.3480555354382549},
            {"embeddings": r'$baai_S$', "dataset": "Corporate", "F1 Score": 0.2935839848627154},

            {"embeddings": r'$baai_L$', "dataset": "DBpedia (EN)", "F1 Score": 0.5475664755245478},
            {"embeddings": r'$baai_L$', "dataset": "DBpedia (EN)", "F1 Score": 0.5454894879751043},
            {"embeddings": r'$baai_L$', "dataset": "DBpedia (EN)", "F1 Score": 0.5980675247123317},

            {"embeddings": r'$baai_L$', "dataset": "DBpedia (ES)", "F1 Score": 0.4558814141873955},
            {"embeddings": r'$baai_L$', "dataset": "DBpedia (ES)", "F1 Score": 0.45194163264032927},
            {"embeddings": r'$baai_L$', "dataset": "DBpedia (ES)", "F1 Score": 0.47112991203315463},

            {"embeddings": r'$baai_L$', "dataset": "Corporate", "F1 Score": 0.28408004406959564},
            {"embeddings": r'$baai_L$', "dataset": "Corporate", "F1 Score": 0.2966222832699755},
            {"embeddings": r'$baai_L$', "dataset": "Corporate", "F1 Score": 0.28276904187048557},

            {"embeddings": r'$sbert_S$', "dataset": "DBpedia (EN)", "F1 Score": 0.5506992821827018},
            {"embeddings": r'$sbert_S$', "dataset": "DBpedia (EN)", "F1 Score": 0.5638360047242182},
            {"embeddings": r'$sbert_S$', "dataset": "DBpedia (EN)", "F1 Score": 0.5516150178428872},

            {"embeddings": r'$sbert_S$', "dataset": "DBpedia (ES)", "F1 Score": 0.40818119903175726},
            {"embeddings": r'$sbert_S$', "dataset": "DBpedia (ES)", "F1 Score": 0.39554361501977503},
            {"embeddings": r'$sbert_S$', "dataset": "DBpedia (ES)", "F1 Score": 0.3990106548757198},

            {"embeddings": r'$sbert_S$', "dataset": "Corporate", "F1 Score": 0.28984049357968716},
            {"embeddings": r'$sbert_S$', "dataset": "Corporate", "F1 Score": 0.28627894086205463},
            {"embeddings": r'$sbert_S$', "dataset": "Corporate", "F1 Score": 0.30933552349510784},

            {"embeddings": r'$sbert_M$', "dataset": "DBpedia (EN)", "F1 Score": 0.5687752461961733},
            {"embeddings": r'$sbert_M$', "dataset": "DBpedia (EN)", "F1 Score": 0.5922204789182033},
            {"embeddings": r'$sbert_M$', "dataset": "DBpedia (EN)", "F1 Score": 0.5704949816495726},

            {"embeddings": r'$sbert_M$', "dataset": "DBpedia (ES)", "F1 Score": 0.5705790029500079},
            {"embeddings": r'$sbert_M$', "dataset": "DBpedia (ES)", "F1 Score": 0.5723625811112105},
            {"embeddings": r'$sbert_M$', "dataset": "DBpedia (ES)", "F1 Score": 0.589287526153517},

            {"embeddings": r'$sbert_M$', "dataset": "Corporate", "F1 Score": 0.3066348402080552},
            {"embeddings": r'$sbert_M$', "dataset": "Corporate", "F1 Score": 0.3013348198566775},
            {"embeddings": r'$sbert_M$', "dataset": "Corporate", "F1 Score": 0.28722810388426323},

            {"embeddings": r'$jinaai_L$', "dataset": "DBpedia (EN)", "F1 Score": 0.5073148043481993},
            {"embeddings": r'$jinaai_L$', "dataset": "DBpedia (EN)", "F1 Score": 0.5189132669051709},
            {"embeddings": r'$jinaai_L$', "dataset": "DBpedia (EN)", "F1 Score": 0.5117392355032914},

            {"embeddings": r'$jinaai_L$', "dataset": "DBpedia (ES)", "F1 Score": 0.5754993738730411},
            {"embeddings": r'$jinaai_L$', "dataset": "DBpedia (ES)", "F1 Score": 0.5608449975226917},
            {"embeddings": r'$jinaai_L$', "dataset": "DBpedia (ES)", "F1 Score": 0.5408470938035168},

            {"embeddings": r'$jinaai_L$', "dataset": "Corporate", "F1 Score": 0.2826639372040017},
            {"embeddings": r'$jinaai_L$', "dataset": "Corporate", "F1 Score": 0.3030665812878233},
            {"embeddings": r'$jinaai_L$', "dataset": "Corporate", "F1 Score": 0.3058849277278708},

        ]
    )

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

    plot_hyperparameter_tuning_results(proportion_results=proportion_results,
                                       embeddings_results=embeddings_results,
                                       examples_results=examples_results,
                                       save_plot=False,
                                    )