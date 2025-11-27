import os
import sqlite3
import time

from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns

"""
Plot the experiment results for TEXT2SPARQL
"""

def plot_hyperparameter_tuning_results(proportion_results: pd.DataFrame,
                                       embeddings_results: pd.DataFrame,
                                       examples_results: pd.DataFrame,
                                       ablation_results: pd.DataFrame,
                                       baseline_results: pd.DataFrame,
                                       model_results: pd.DataFrame,
                                       save_plot: bool = False) -> None:
    """Plot the hyperparameter tuning results for TEXT2SPARQL"""
    
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=3)
    fig = plt.figure(figsize=(20, 20))
    gs = GridSpec(3, 4, figure=fig)

    ax = [fig.add_subplot(gs[0, 0:2]), 
          fig.add_subplot(gs[0, 2:4]), 
          fig.add_subplot(gs[1, 0:2]), 
          fig.add_subplot(gs[1, 2:4]),
          fig.add_subplot(gs[2, 1:3]),
        ]

    plt.subplots_adjust(hspace=.5, wspace=3)

    # First subplot - proportion tuning
    sns.lineplot(
        data=proportion_results,
        x="proportion",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        linewidth=5,
        palette=sns.color_palette("Set2")[:3],
        ax=ax[0],
    )

    ax[0].set_title("(i) Fraction of Provided Schema", fontweight="bold", y=1.05)
    ax[0].set_xlim(0, 1)
    ax[0].set_xticks([.0, .25, .5, .75, 1.0], ["0%", '25%', "50%", '75%', "100%"])
    ax[0].set_xlabel("")
    ax[0].set_ylim(0, .75)
    ax[0].set_yticks([.1, .2, .3, .4, .5, .6, .7], [".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax[0].get_legend().remove()

    # Second subplot - embeddings tuning
    sns.barplot(
        data=embeddings_results,
        x="F1 Score",
        y="embeddings",
        hue="dataset",
        orient="h",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        palette=sns.color_palette("Set2")[:3],
        ax=ax[1],
    )
    
    ax[1].set_title("(ii) Embeddings Model", fontweight="bold", y=1.05)
    ax[1].set_xlim(0, .7)
    ax[1].set_xticks([0, .1, .2, .3, .4, .5, .6, .7], ["0", ".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax[1].set_ylabel("")
    ax[1].get_legend().remove()


    # Third subplot - examples tuning
    sns.lineplot(
        data=examples_results,
        x="examples",
        y="F1 Score",
        hue="dataset",
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        linewidth=5,
        palette=sns.color_palette("Set2")[:3],
        ax=ax[2],
    )

    ax[2].set_title("(iii) Number of Provided Examples", fontweight="bold", y=1.05)
    ax[2].set_xlim(0, 20)
    ax[2].set_xticks([0, 5, 10, 15, 20], ["0", "5", "10", "15", "20"])
    ax[2].set_xlabel("")
    ax[2].set_ylim(0, .75)
    ax[2].set_yticks([.1, .2, .3, .4, .5, .6, .7], [".1", ".2", ".3", ".4", ".5", ".6", ".7"])    
    ax[2].get_legend().remove()

    # Fourth subplot - model selection
    sns.barplot(
        data=model_results,
        x="F1 Score",
        y="model",
        hue="dataset",
        orient="h", 
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        palette=sns.color_palette("Set2")[:3],
        ax=ax[3],
    )

    ax[3].set_title("(iv) Large Language Model", fontweight="bold", y=1.05)
    ax[3].set_xlim(0, .7)
    ax[3].set_xticks([0, .1, .2, .3, .4, .5, .6, .7], ["0", ".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax[3].set_ylabel("")
    ax[3].get_legend().remove()
    
    # Fifth subplot - ablation study
    sns.barplot(
        data=ablation_results,
        x="F1 Score",
        y="component",
        hue="dataset",
        orient="h", 
        hue_order=["DBpedia (EN)", "DBpedia (ES)", "Corporate"],
        palette=sns.color_palette("Set2")[:3],
        ax=ax[4],
    )

    ax[4].axvline(baseline_results[baseline_results['dataset'] == 'DBpedia (EN)']['F1 Score'].mean(), color=sns.color_palette("Set2")[0], linestyle='--', linewidth=5)
    ax[4].axvline(baseline_results[baseline_results['dataset'] == 'DBpedia (ES)']['F1 Score'].mean(), color=sns.color_palette("Set2")[1], linestyle='--', linewidth=5)
    ax[4].axvline(baseline_results[baseline_results['dataset'] == 'Corporate']['F1 Score'].mean(), color=sns.color_palette("Set2")[2], linestyle='--', linewidth=5)

    ax[4].set_title("(v) Ablation Study", fontweight="bold", y=1.05)
    ax[4].set_xlim(0, .7)
    ax[4].set_xticks([0, .1, .2, .3, .4, .5, .6, .7], ["0", ".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax[4].set_ylabel("")
    ax[4].get_legend().remove()


    fig.legend(*ax[1].get_legend_handles_labels(), bbox_to_anchor=(0.5, 1), loc='upper center', ncol=3, title="TEXT2SPARQL Corpus")
    sns.despine(top=True, right=True)

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_hyperparameter_tuning.png"), bbox_inches="tight")
    else:
        plt.show()


def plot_overall_results(overall_results: pd.DataFrame,
                         sota_results: pd.DataFrame,
                         save_plot: bool = False) -> None:
    """Plot the overall results for TEXT2SPARQL"""
    
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=4.5)
    fig = plt.figure(figsize=(20, 10))
    ax = plt.gca()

    # Overall results
    sns.barplot(
        data=overall_results,
        x="F1 Score",
        y="dataset",
        hue="model",
        orient="h",
        palette=sns.color_palette("Set1")[:3],
        ax=ax,
    )

    #SOTA results
    ax.axvline(sota_results[sota_results['dataset'] == 'DBpedia (EN)']['F1 Score'].iloc[0], ymin=.66, ymax=1, color=sns.color_palette("Set1")[3], linestyle='--', linewidth=9, label="TEXT2SPARQL Winners")
    ax.axvline(sota_results[sota_results['dataset'] == 'DBpedia (ES)']['F1 Score'].iloc[0], ymin=.33, ymax=.66, color=sns.color_palette("Set1")[3], linestyle='--', linewidth=9)
    ax.axvline(sota_results[sota_results['dataset'] == 'Corporate']['F1 Score'].iloc[0], ymin=0, ymax=.33, color=sns.color_palette("Set1")[3], linestyle='--', linewidth=9)

    ax.set_xlim(0, .7)
    ax.set_xticks([0, .1, .2, .3, .4, .5, .6, .7], ["0", ".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax.set_ylabel("")
    ax.get_legend().remove()

    fig.legend(*ax.get_legend_handles_labels(), bbox_to_anchor=(0.5, 1.3), loc='upper center', ncol=2, title="System")
    sns.despine(top=True, right=True)
    plt.tight_layout()

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_overall_results.png"), bbox_inches="tight")
    else:
        plt.show()


def plot_cost_analysis_results(cost_results: pd.DataFrame,
                               sota_time_results: pd.DataFrame,
                               save_plot: bool = False) -> None:
    """Plot the cost analysis results for TEXT2SPARQL"""

    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=4.5)
    fig = plt.figure(figsize=(30, 10))
    gs = GridSpec(1, 3, figure=fig)

    ax = [fig.add_subplot(gs[0, 0:1]), 
          fig.add_subplot(gs[0, 1:2]), 
          fig.add_subplot(gs[0, 2:3]), 
        ]

    #Transform results
    results = []
    for _, res in cost_results.iterrows():
        for dataset, metrics in res['results'].items():
            for llm_time, input_tokens, output_tokens in zip(metrics["llm_time"], metrics["input_tokens"], metrics["output_tokens"]):
                results.append({
                    "model": res["model"],
                    "dataset": dataset,
                    "llm_time": llm_time,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })
    results = pd.DataFrame(results)


    # LLM time
    sns.boxplot(
        data=results,
        x="llm_time",
        y="dataset",
        hue="model",
        orient='h',
        palette=sns.color_palette("Set1")[:3],
        ax=ax[0],
    )

    #SOTA results
    ax[0].axvline(sota_time_results[sota_time_results['dataset'] == 'DBpedia (EN)']['time'].iloc[0], ymin=.66, ymax=1, color=sns.color_palette("Set1")[3], linestyle='--', linewidth=9, label="TEXT2SPARQL Winners")
    ax[0].axvline(sota_time_results[sota_time_results['dataset'] == 'Corporate']['time'].iloc[0], ymin=0, ymax=.33, color=sns.color_palette("Set1")[3], linestyle='--', linewidth=9)

    ax[0].set_title("(i) Runtime (seconds)", fontweight="bold", y=1.05)
    ax[0].set_xlabel("")
    ax[0].set_xscale('log')
    ax[0].set_ylabel("")
    ax[0].get_legend().remove()

    # Input tokens
    sns.boxplot(
        data=results,
        x="input_tokens",
        y="dataset",
        hue="model",
        orient='h',
        palette=sns.color_palette("Set1")[:3],
        ax=ax[1],
    )

    ax[1].set_title("(ii) Input Tokens", fontweight="bold", y=1.05)
    ax[1].set_xlabel("")
    ax[1].set_xlim(100, 10000)
    ax[1].set_xscale('log')
    ax[1].set_ylabel("")
    ax[1].set_yticklabels("")
    ax[1].get_legend().remove()


    # Output tokens
    sns.boxplot(
        data=results,
        x="output_tokens",
        y="dataset",
        hue="model",
        orient='h',
        palette=sns.color_palette("Set1")[:3],
        ax=ax[2],
    )

    ax[2].set_title("(iii) Output Tokens", fontweight="bold", y=1.05)
    ax[2].set_xlabel("")
    ax[2].set_xlim(10, 10000)
    ax[2].set_xscale('log')
    ax[2].set_ylabel("")
    ax[2].set_yticklabels("")
    ax[2].get_legend().remove()

    fig.legend(*ax[0].get_legend_handles_labels(), bbox_to_anchor=(0.5, 1.3), loc='upper center', ncol=2, title="System")
    sns.despine(top=True, right=True)

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_cost_results.png"), bbox_inches="tight")
    else:
        plt.show()

def plot_bio_results(bio_results: pd.DataFrame,
                         save_plot: bool = False) -> None:
    """Plot the bio results for TEXT2SPARQL"""
    
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=4.5)
    fig = plt.figure(figsize=(20, 10))
    ax = plt.gca()

    # Bio results
    sns.barplot(
        data=bio_results,
        x="F1 Score",
        y="dataset",
        hue="model",
        orient="h",
        palette=sns.color_palette("Set1")[:3],
        ax=ax,
    )

    ax.set_xlim(0, .7)
    ax.set_xticks([0, .1, .2, .3, .4, .5, .6, .7], ["0", ".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax.set_ylabel("")
    ax.get_legend().remove()

    fig.legend(*ax.get_legend_handles_labels(), bbox_to_anchor=(0.5, 1.2), loc='upper center', ncol=3, title="System")
    sns.despine(top=True, right=True)
    plt.tight_layout()

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_bio_results.png"), bbox_inches="tight")
    else:
        plt.show()


if __name__ == "__main__":
    proportion_results = pd.DataFrame(
        [
            {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": 0.6360229918901611},
            {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5718582242376377},
            {"proportion": 0.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5554370701081763},

            {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": 0.5450238770948749},
            {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": 0.5837238113312996},
            {"proportion": 0.00, "dataset": "DBpedia (ES)", "F1 Score": 0.598329013074588},

            {"proportion": 0.00, "dataset": "Corporate", "F1 Score": 0.2031790577448751},
            {"proportion": 0.00, "dataset": "Corporate", "F1 Score": 0.24414868849773605},
            {"proportion": 0.00, "dataset": "Corporate", "F1 Score": 0.24802115887574275},


            {"proportion": 0.25, "dataset": "DBpedia (EN)", "F1 Score": 0.6302217769142227},
            {"proportion": 0.25, "dataset": "DBpedia (EN)", "F1 Score": 0.6165165258327675},
            {"proportion": 0.25, "dataset": "DBpedia (EN)", "F1 Score": 0.6152837403969743},

            {"proportion": 0.25, "dataset": "DBpedia (ES)", "F1 Score": 0.6009851382878372},
            {"proportion": 0.25, "dataset": "DBpedia (ES)", "F1 Score": 0.6120562795695946},
            {"proportion": 0.25, "dataset": "DBpedia (ES)", "F1 Score": 0.5980699251812547},

            {"proportion": 0.25, "dataset": "Corporate", "F1 Score": 0.18958407378647435},
            {"proportion": 0.25, "dataset": "Corporate", "F1 Score": 0.20434082503986997},
            {"proportion": 0.25, "dataset": "Corporate", "F1 Score": 0.20655927139301258},


            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.54930383335061},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.574743837707901},
            {"proportion": 0.50, "dataset": "DBpedia (EN)", "F1 Score": 0.5824336953958507},

            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.5721117546925543},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.5941271118380055},
            {"proportion": 0.50, "dataset": "DBpedia (ES)", "F1 Score": 0.5698079818519586},

            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.287991639066309},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.27100247168667335},
            {"proportion": 0.50, "dataset": "Corporate", "F1 Score": 0.24748994220399465},


            {"proportion": 0.75, "dataset": "DBpedia (EN)", "F1 Score": 0.5879848961871974},
            {"proportion": 0.75, "dataset": "DBpedia (EN)", "F1 Score": 0.582223151283596},
            {"proportion": 0.75, "dataset": "DBpedia (EN)", "F1 Score": 0.5777030831560765},

            {"proportion": 0.75, "dataset": "DBpedia (ES)", "F1 Score": 0.5925861882869196},
            {"proportion": 0.75, "dataset": "DBpedia (ES)", "F1 Score": 0.5470734514947754},
            {"proportion": 0.75, "dataset": "DBpedia (ES)", "F1 Score": 0.5719511332591165},

            {"proportion": 0.75, "dataset": "Corporate", "F1 Score": 0.3051135728013111},
            {"proportion": 0.75, "dataset": "Corporate", "F1 Score": 0.3088665517369803},
            {"proportion": 0.75, "dataset": "Corporate", "F1 Score": 0.32515303249061434},


            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5538934933746682},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.6219437568379328},
            {"proportion": 1.00, "dataset": "DBpedia (EN)", "F1 Score": 0.5702833245723039},

            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.5821023758373475},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.5695760289633164},
            {"proportion": 1.00, "dataset": "DBpedia (ES)", "F1 Score": 0.5719686020657035},

            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.30426983266657703},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.3209482793891293},
            {"proportion": 1.00, "dataset": "Corporate", "F1 Score": 0.2930558631633798},
        ]
    )

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
            {"examples": 0, "dataset": "DBpedia (EN)", "F1 Score": 0.2669183689242966},
            {"examples": 0, "dataset": "DBpedia (EN)", "F1 Score": 0.2648311874783169},
            {"examples": 0, "dataset": "DBpedia (EN)", "F1 Score": 0.25614395814988583},
            {"examples": 5, "dataset": "DBpedia (EN)", "F1 Score": 0.5175819376333841},
            {"examples": 5, "dataset": "DBpedia (EN)", "F1 Score": 0.5018598089257685},
            {"examples": 5, "dataset": "DBpedia (EN)", "F1 Score": 0.5100795246926575},
            {"examples": 10, "dataset": "DBpedia (EN)", "F1 Score": 0.5687752461961733},
            {"examples": 10, "dataset": "DBpedia (EN)", "F1 Score": 0.5922204789182033},
            {"examples": 10, "dataset": "DBpedia (EN)", "F1 Score": 0.5704949816495726},
            {"examples": 15, "dataset": "DBpedia (EN)", "F1 Score": 0.5767038192589087},
            {"examples": 15, "dataset": "DBpedia (EN)", "F1 Score": 0.60244374699482},
            {"examples": 15, "dataset": "DBpedia (EN)", "F1 Score": 0.5513844299343054},
            {"examples": 20, "dataset": "DBpedia (EN)", "F1 Score": 0.5779453735120814},
            {"examples": 20, "dataset": "DBpedia (EN)", "F1 Score": 0.5941432825125542},
            {"examples": 20, "dataset": "DBpedia (EN)", "F1 Score": 0.5984300094005004},

            {"examples": 0, "dataset": "DBpedia (ES)", "F1 Score": 0.23942766903879126},
            {"examples": 0, "dataset": "DBpedia (ES)", "F1 Score": 0.22342740782734746},
            {"examples": 0, "dataset": "DBpedia (ES)", "F1 Score": 0.24673908560233304},
            {"examples": 5, "dataset": "DBpedia (ES)", "F1 Score": 0.5319959175128429},
            {"examples": 5, "dataset": "DBpedia (ES)", "F1 Score": 0.5351754601255854},
            {"examples": 5, "dataset": "DBpedia (ES)", "F1 Score": 0.5126104192720157},
            {"examples": 10, "dataset": "DBpedia (ES)", "F1 Score": 0.5705790029500079},
            {"examples": 10, "dataset": "DBpedia (ES)", "F1 Score": 0.5723625811112105},
            {"examples": 10, "dataset": "DBpedia (ES)", "F1 Score": 0.589287526153517},
            {"examples": 15, "dataset": "DBpedia (ES)", "F1 Score": 0.580612519948761},
            {"examples": 15, "dataset": "DBpedia (ES)", "F1 Score": 0.601802618694283},
            {"examples": 15, "dataset": "DBpedia (ES)", "F1 Score": 0.5774310902798893},
            {"examples": 20, "dataset": "DBpedia (ES)", "F1 Score": 0.5727977998118812},
            {"examples": 20, "dataset": "DBpedia (ES)", "F1 Score": 0.5471270363354414},
            {"examples": 20, "dataset": "DBpedia (ES)", "F1 Score": 0.5891981536215178},

            {"examples": 0, "dataset": "Corporate", "F1 Score": 0.26983264166750176},
            {"examples": 0, "dataset": "Corporate", "F1 Score": 0.2912720356068957},
            {"examples": 0, "dataset": "Corporate", "F1 Score": 0.30635243887382946},
            {"examples": 5, "dataset": "Corporate", "F1 Score": 0.31182862447217996},
            {"examples": 5, "dataset": "Corporate", "F1 Score": 0.2544413502982772},
            {"examples": 5, "dataset": "Corporate", "F1 Score": 0.2752784944777997},
            {"examples": 10, "dataset": "Corporate", "F1 Score": 0.3066348402080552},
            {"examples": 10, "dataset": "Corporate", "F1 Score": 0.3013348198566775},
            {"examples": 10, "dataset": "Corporate", "F1 Score": 0.28722810388426323},
            {"examples": 15, "dataset": "Corporate", "F1 Score": 0.3371504832592741},
            {"examples": 15, "dataset": "Corporate", "F1 Score": 0.3347155497717091},
            {"examples": 15, "dataset": "Corporate", "F1 Score": 0.31489712258486086},
            {"examples": 20, "dataset": "Corporate", "F1 Score": 0.3172732269160719},
            {"examples": 20, "dataset": "Corporate", "F1 Score": 0.31406279363728284},
            {"examples": 20, "dataset": "Corporate", "F1 Score": 0.2903667217004962},
        ]
    )

    ablation_results = pd.DataFrame(
        [
            {"component": "w/o Examples", "dataset": "DBpedia (EN)", "F1 Score": 0.2669183689242966},
            {"component": "w/o Examples", "dataset": "DBpedia (EN)", "F1 Score": 0.2648311874783169},
            {"component": "w/o Examples", "dataset": "DBpedia (EN)", "F1 Score": 0.25614395814988583},

            {"component": "w/o Examples", "dataset": "DBpedia (ES)", "F1 Score": 0.23942766903879126},
            {"component": "w/o Examples", "dataset": "DBpedia (ES)", "F1 Score": 0.22342740782734746},
            {"component": "w/o Examples", "dataset": "DBpedia (ES)", "F1 Score": 0.24673908560233304},

            {"component": "w/o Examples", "dataset": "Corporate", "F1 Score": 0.26983264166750176},
            {"component": "w/o Examples", "dataset": "Corporate", "F1 Score": 0.2912720356068957},
            {"component": "w/o Examples", "dataset": "Corporate", "F1 Score": 0.30635243887382946},


            {"component": "w/o Full Schema", "dataset": "DBpedia (EN)", "F1 Score": 0.6360229918901611},
            {"component": "w/o Full Schema", "dataset": "DBpedia (EN)", "F1 Score": 0.5718582242376377},
            {"component": "w/o Full Schema", "dataset": "DBpedia (EN)", "F1 Score": 0.5554370701081763},

            {"component": "w/o Full Schema", "dataset": "DBpedia (ES)", "F1 Score": 0.5450238770948749},
            {"component": "w/o Full Schema", "dataset": "DBpedia (ES)", "F1 Score": 0.5837238113312996},
            {"component": "w/o Full Schema", "dataset": "DBpedia (ES)", "F1 Score": 0.598329013074588},

            {"component": "w/o Full Schema", "dataset": "Corporate", "F1 Score": 0.2031790577448751},
            {"component": "w/o Full Schema", "dataset": "Corporate", "F1 Score": 0.24414868849773605},
            {"component": "w/o Full Schema", "dataset": "Corporate", "F1 Score": 0.24802115887574275},


            {"component": "w/o Property Ranges", "dataset": "DBpedia (EN)", "F1 Score": 0.5906921625259051},
            {"component": "w/o Property Ranges", "dataset": "DBpedia (EN)", "F1 Score": 0.5729729935425972},
            {"component": "w/o Property Ranges", "dataset": "DBpedia (EN)", "F1 Score": 0.6142224484164015},

            {"component": "w/o Property Ranges", "dataset": "DBpedia (ES)", "F1 Score": 0.5851865249984981},
            {"component": "w/o Property Ranges", "dataset": "DBpedia (ES)", "F1 Score": 0.5528209608497341},
            {"component": "w/o Property Ranges", "dataset": "DBpedia (ES)", "F1 Score": 0.569014812654553},

            {"component": "w/o Property Ranges", "dataset": "Corporate", "F1 Score": 0.30838101384390915},
            {"component": "w/o Property Ranges", "dataset": "Corporate", "F1 Score": 0.33423939199428354},
            {"component": "w/o Property Ranges", "dataset": "Corporate", "F1 Score": 0.313871063595153},


            {"component": "w/o Properties", "dataset": "DBpedia (EN)", "F1 Score": 0.568181389961076},
            {"component": "w/o Properties", "dataset": "DBpedia (EN)", "F1 Score": 0.6014872209186768},
            {"component": "w/o Properties", "dataset": "DBpedia (EN)", "F1 Score": 0.5987622338489511},

            {"component": "w/o Properties", "dataset": "DBpedia (ES)", "F1 Score": 0.5983425449248978},
            {"component": "w/o Properties", "dataset": "DBpedia (ES)", "F1 Score": 0.5582213460007434},
            {"component": "w/o Properties", "dataset": "DBpedia (ES)", "F1 Score": 0.6132176856107568},

            {"component": "w/o Properties", "dataset": "Corporate", "F1 Score": 0.33211091121276765},
            {"component": "w/o Properties", "dataset": "Corporate", "F1 Score": 0.3275006543895829},
            {"component": "w/o Properties", "dataset": "Corporate", "F1 Score": 0.3347648100153243},


            {"component": "w/o Ordered Properties", "dataset": "DBpedia (EN)", "F1 Score": 0.6065900836905909},
            {"component": "w/o Ordered Properties", "dataset": "DBpedia (EN)", "F1 Score": 0.5622403584999244},
            {"component": "w/o Ordered Properties", "dataset": "DBpedia (EN)", "F1 Score": 0.6003009892571323},

            {"component": "w/o Ordered Properties", "dataset": "DBpedia (ES)", "F1 Score": 0.6040960485987151},
            {"component": "w/o Ordered Properties", "dataset": "DBpedia (ES)", "F1 Score": 0.5563590217561157},
            {"component": "w/o Ordered Properties", "dataset": "DBpedia (ES)", "F1 Score": 0.5789829545878117},

            {"component": "w/o Ordered Properties", "dataset": "Corporate", "F1 Score": 0.33383963736294997},
            {"component": "w/o Ordered Properties", "dataset": "Corporate", "F1 Score": 0.3447317848854021},
            {"component": "w/o Ordered Properties", "dataset": "Corporate", "F1 Score": 0.3542555944092116},


            {"component": "w/o Validation", "dataset": "DBpedia (EN)", "F1 Score": 0.533343045459905},
            {"component": "w/o Validation", "dataset": "DBpedia (EN)", "F1 Score": 0.5658815976305689},
            {"component": "w/o Validation", "dataset": "DBpedia (EN)", "F1 Score": 0.5745202086111378},

            {"component": "w/o Validation", "dataset": "DBpedia (ES)", "F1 Score": 0.5750723899672247},
            {"component": "w/o Validation", "dataset": "DBpedia (ES)", "F1 Score": 0.5681937665580514},
            {"component": "w/o Validation", "dataset": "DBpedia (ES)", "F1 Score": 0.555735045835838},

            {"component": "w/o Validation", "dataset": "Corporate", "F1 Score": 0.2943066566442385},
            {"component": "w/o Validation", "dataset": "Corporate", "F1 Score": 0.2876539538875469},
            {"component": "w/o Validation", "dataset": "Corporate", "F1 Score": 0.2913847307301178},
        ]
    )

    baseline_results = pd.DataFrame(
        [
            {"dataset": "DBpedia (EN)", "F1 Score": 0.5767038192589087},
            {"dataset": "DBpedia (EN)", "F1 Score": 0.60244374699482},
            {"dataset": "DBpedia (EN)", "F1 Score": 0.5513844299343054},

            {"dataset": "DBpedia (ES)", "F1 Score": 0.580612519948761},
            {"dataset": "DBpedia (ES)", "F1 Score": 0.601802618694283},
            {"dataset": "DBpedia (ES)", "F1 Score": 0.5774310902798893},

            {"dataset": "Corporate", "F1 Score": 0.3371504832592741},
            {"dataset": "Corporate", "F1 Score": 0.3347155497717091},
            {"dataset": "Corporate", "F1 Score": 0.31489712258486086},
        ]
    )

    model_results = pd.DataFrame(
        [
            {"model": "GPT-4o", "dataset": "DBpedia (EN)", "F1 Score": 0.6690007929066105},
            {"model": "GPT-4o", "dataset": "DBpedia (EN)", "F1 Score": 0.6741166794466641},
            {"model": "GPT-4o", "dataset": "DBpedia (EN)", "F1 Score": 0.6952634191692368},

            {"model": "GPT-4o", "dataset": "DBpedia (ES)", "F1 Score": 0.6542033975373135},
            {"model": "GPT-4o", "dataset": "DBpedia (ES)", "F1 Score": 0.6673643826702074},
            {"model": "GPT-4o", "dataset": "DBpedia (ES)", "F1 Score": 0.6547826165049525},

            {"model": "GPT-4o", "dataset": "Corporate", "F1 Score": 0.4403431543419664},
            {"model": "GPT-4o", "dataset": "Corporate", "F1 Score": 0.4302794586250879},
            {"model": "GPT-4o", "dataset": "Corporate", "F1 Score": 0.422015569736199},


            {"model": "Mistral Large 2", "dataset": "DBpedia (EN)", "F1 Score": 0.6158133022707935},
            {"model": "Mistral Large 2", "dataset": "DBpedia (EN)", "F1 Score": 0.6378097240848767},
            {"model": "Mistral Large 2", "dataset": "DBpedia (EN)", "F1 Score": 0.639661724438893},

            {"model": "Mistral Large 2", "dataset": "DBpedia (ES)", "F1 Score": 0.6173390843710245},
            {"model": "Mistral Large 2", "dataset": "DBpedia (ES)", "F1 Score": 0.6385462028291864},
            {"model": "Mistral Large 2", "dataset": "DBpedia (ES)", "F1 Score": 0.5954783065195792},

            {"model": "Mistral Large 2", "dataset": "Corporate", "F1 Score": 0.3519455883649196},
            {"model": "Mistral Large 2", "dataset": "Corporate", "F1 Score": 0.3937408005317151},
            {"model": "Mistral Large 2", "dataset": "Corporate", "F1 Score": 0.37801075055609973},


            {"model": "Qwen 2.5", "dataset": "DBpedia (EN)", "F1 Score": 0.6547218955648587},
            {"model": "Qwen 2.5", "dataset": "DBpedia (EN)", "F1 Score": 0.6281601327082715},
            {"model": "Qwen 2.5", "dataset": "DBpedia (EN)", "F1 Score": 0.639456669887195},

            {"model": "Qwen 2.5", "dataset": "DBpedia (ES)", "F1 Score": 0.657979863784743},
            {"model": "Qwen 2.5", "dataset": "DBpedia (ES)", "F1 Score": 0.6065074932377659},
            {"model": "Qwen 2.5", "dataset": "DBpedia (ES)", "F1 Score": 0.6715895763806423},

            {"model": "Qwen 2.5", "dataset": "Corporate", "F1 Score": 0.36899632381966513},
            {"model": "Qwen 2.5", "dataset": "Corporate", "F1 Score": 0.4051732408777085},
            {"model": "Qwen 2.5", "dataset": "Corporate", "F1 Score": 0.40369778490671704},


            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (EN)", "F1 Score": 0.6386270211114444},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (EN)", "F1 Score": 0.63303831649836},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (EN)", "F1 Score": 0.6268120605933296},

            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (ES)", "F1 Score": 0.6127242079833665},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (ES)", "F1 Score": 0.6112838696518457},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (ES)", "F1 Score": 0.605261842929127},

            {"model": "Claude 3.5 Sonnet", "dataset": "Corporate", "F1 Score": 0.42633112866753614},
            {"model": "Claude 3.5 Sonnet", "dataset": "Corporate", "F1 Score": 0.41622769688085254},
            {"model": "Claude 3.5 Sonnet", "dataset": "Corporate", "F1 Score": 0.39020052153339546},

        ]
    )

    sota_results = pd.DataFrame(
        [
            {"dataset": "DBpedia (EN)", "F1 Score": 0.5457413082401525},
            {"dataset": "DBpedia (ES)", "F1 Score": 0.536993561548598},
            {"dataset": "Corporate", "F1 Score": 0.4360979995467166},
        ]
    )

    overall_results = pd.DataFrame(
        [
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "DBpedia (EN)", "F1 Score": 0.6690007929066105},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "DBpedia (EN)", "F1 Score": 0.6741166794466641},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "DBpedia (EN)", "F1 Score": 0.6952634191692368},

            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "DBpedia (ES)", "F1 Score": 0.6542033975373135},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "DBpedia (ES)", "F1 Score": 0.6673643826702074},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "DBpedia (ES)", "F1 Score": 0.6547826165049525},

            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Corporate", "F1 Score": 0.4403431543419664},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Corporate", "F1 Score": 0.4302794586250879},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Corporate", "F1 Score": 0.422015569736199},


            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "DBpedia (EN)", "F1 Score": 0.5538934933746682},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "DBpedia (EN)", "F1 Score": 0.6219437568379328},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "DBpedia (EN)", "F1 Score": 0.5702833245723039},

            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "DBpedia (ES)", "F1 Score": 0.5821023758373475},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "DBpedia (ES)", "F1 Score": 0.5695760289633164},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "DBpedia (ES)", "F1 Score": 0.5719686020657035},

            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Corporate", "F1 Score": 0.30426983266657703},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Corporate", "F1 Score": 0.3209482793891293},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Corporate", "F1 Score": 0.2930558631633798},


            {"model": r'$SPARQL-LLM_{os}$', "dataset": "DBpedia (EN)", "F1 Score": 0.5998776412277721},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "DBpedia (EN)", "F1 Score": 0.6022912865534492},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "DBpedia (EN)", "F1 Score": 0.6173177711620293},

            {"model": r'$SPARQL-LLM_{os}$', "dataset": "DBpedia (ES)", "F1 Score": 0.6035723760980651},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "DBpedia (ES)", "F1 Score": 0.6073406666144291},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "DBpedia (ES)", "F1 Score": 0.6015790104623291},

            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Corporate", "F1 Score": 0.42715717702918965},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Corporate", "F1 Score": 0.42474821066090257},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Corporate", "F1 Score": 0.4926209413214926},
        ]
    )

    cost_results = pd.DataFrame(
        [
            {"model": r'$SPARQL-LLM_{lg}$', "results": {"DBpedia (EN)":{"llm_time":[3.2507606270000906,4.870101960000056,2.340208250999922,7.394708254000079,7.622475461000022,3.7237960020001992,9.299295045999997,1.9151975010001934,1.9251061669999672,2.5428032929999063,4.256744710000021,2.3312958750000234,2.7948842929999955,4.137462001999893,1.7394115419999707,2.1146445839999615,2.3143529589999616,2.445623168000111,1.9909414180001477,2.91610925100008,4.149645210000017,3.9690964609999355,3.561696668000195,3.7040029600000253,2.0779751679999663,2.250181252000175,2.3568128340000385,2.738712625999824,2.6118835429999763,3.1032185010001285,2.263365042000032,3.450328000999889,2.3113702929999818,3.563274710000087,3.0504660430001422,3.9701989600000616,1.9719260009999289,3.8326457509999727,2.277323043000024,3.7401454600001216,2.220294501000126,3.990437209999982,4.910934378000093,2.403151750999996,2.653305416999956,5.312821043999975,3.5792623770000773,2.679320584999914,1.9614952510000876,2.356954291999955,4.752889211000138,2.4664405429998624,2.250736459000109,2.5066916680000304,2.30648204299996,3.505073125999843,3.2647910430000593,1.8456977089999782,2.654515167999989,2.9860216269999,2.7029816259998825,2.303794792999952,17.78171417600015,2.603617751999991,2.2512895429999844,3.547217416999956,5.281757877000018,3.444296667999879,2.3670055429997774,2.243127084000207,28.381421720999697,2.6607969169999706,2.743344834000254,2.7432902090004063,2.5619959180003207,1.940934709999965,21.05219921700018,4.0203768350002065,5.45675066900003,4.988097960999767,3.2709268349999547,17.262082548999842,22.080061759999808,1.8189526260002822,28.570606470999792,3.503622085999723,3.199923085000137,3.056112793000011,6.923214963000191,3.303615085000274,3.1463911270002427,32.59438843199996,11.053911589000109,1.9341434179996213,4.780836043999898,3.5497069599996394,15.948169631999463,6.142186294000567,5.0084579189997385],"input_tokens":[5204,5633,5143,190,5648,5077,158,5391,4733,5687,5078,5855,5367,5207,5297,5049,5377,5423,5283,4967,5378,5435,5277,5022,5324,5585,5206,5247,5297,5211,5424,5699,5401,5547,5460,5204,5046,5464,5234,5296,5365,5813,5604,5416,5402,5245,5647,5236,5386,5465,5145,5358,5487,4981,5264,5426,5268,5050,5568,5619,5388,5546,206,5145,5065,4986,199,5400,5191,5341,186,5072,5640,5410,5424,5206,507,4917,5585,5166,5202,183,234,5282,199,5182,5468,5392,214,5350,5602,797,222,5629,5450,5180,155,216,5252],"output_tokens":[76,92,55,51,61,110,248,57,55,108,107,53,90,59,50,51,87,89,62,83,69,108,96,90,91,56,54,70,61,69,91,71,93,115,81,112,52,106,70,121,70,113,124,68,53,91,112,83,60,62,84,78,69,91,50,109,109,65,93,69,94,55,231,80,64,90,19,52,53,55,306,55,60,55,73,60,280,58,105,111,82,241,274,53,385,107,93,93,34,113,106,376,50,57,106,90,248,16,107]},"DBpedia (ES)":{"llm_time":[2.9030189180000434,3.639595793000126,2.9438557930000115,9.284518586999866,7.624045920000071,3.079026460000023,11.317354295999849,2.2907398350000676,1.9768229179999253,3.2478038760000345,4.456111043999954,2.713916960000006,3.0419010840000738,2.1632598759999837,2.2776795839999977,1.8751536669999496,3.451334459999998,3.583330794000176,1.9851887090001128,2.1329012090000106,3.983444961000032,4.89457496,4.113663876999908,2.3215856260001146,2.948230042999967,4.422023417999981,2.2619792089999464,2.7780334599999605,2.546446292000155,5.195125127999972,2.9220521269999153,2.6969751260000976,4.6405526679998275,4.9850957520000065,3.4357202510000207,3.1842894599999454,1.8676454179999382,3.629529251999884,3.5259097520001887,3.5751148770000327,2.3793950839999525,6.085376043999986,3.953653086000031,2.4469455839998773,2.606841126000063,2.87127779299999,3.067231293000077,2.11138516799997,1.947875083999861,2.1104566260000865,3.1910737939999763,2.968775209999876,1.9683264600000712,1.8418351259999781,1.6293473760001689,3.4534237520001625,4.710739209999929,2.4345020010000553,3.2133187099998395,1.5757108339998922,2.9483864189999167,1.9313130839998394,21.678175634000127,2.4004025429999274,2.2446406260000913,3.1811505850000685,5.3389840859995275,1.8388143350002792,2.827793584999654,2.5440719600001103,23.082504970000628,2.2120937930003493,1.95908029300017,3.170377584999642,2.8104280839997955,2.58734404300003,2.1131860840000627,2.6149504180002623,3.3091339600000538,3.1725413760000265,4.1593915440003,13.576931799000704,16.553881965000528,2.24251491799987,2.414494625000316,3.832543584999712,3.502404585000022,2.6392837520002104,7.456543003000206,3.6019934179998927,2.6418146679998245,23.303657384999042,8.045885126999565,2.0180246260001695,3.4380793350001113,3.2492399180000575,19.59971601000052,6.784545711000192,5.753358252999988],"input_tokens":[5253,5521,5089,198,222,5125,228,5332,4736,5704,5037,5855,5290,5160,5312,5049,5378,5424,5338,4962,5336,5417,5252,5014,5250,5489,5023,5219,5386,5198,5282,5622,5394,5474,5479,5243,5114,5386,5389,5317,5367,5783,5528,5412,5403,5149,5606,5203,5386,5466,5132,5386,5495,5057,5250,5349,5074,5028,5544,5608,5367,5550,216,5017,4914,5171,201,5356,5253,5386,189,4999,5683,5453,5415,5332,5613,4899,5592,5067,5274,217,252,5221,5219,5186,5420,5365,216,5329,5558,770,224,5607,5453,5185,188,205,5256],"output_tokens":[76,92,55,71,58,110,94,57,55,109,104,53,91,59,50,51,86,89,61,82,69,109,96,90,91,56,54,69,61,61,92,70,93,115,81,113,52,105,106,121,69,114,87,72,53,95,112,85,60,62,84,78,69,91,51,108,109,62,92,69,93,55,221,82,63,69,20,52,53,55,340,55,51,52,72,60,78,58,105,110,82,81,224,50,68,107,93,93,59,113,106,407,54,57,96,90,214,14,85]},"Corporate":{"llm_time":[18.541844299999866,1.8753137089997836,2.1307379589998163,6.242349586000273,24.516332301999682,5.084376251999856,2.2600208759999987,35.58249118399954,2.485372625999844,14.571015549000094,2.8240011679999952,8.765207670000564,2.6950894179999523,18.375693633000083,3.635547084999871,1.3765943339999467,1.455653667000206,3.0609099600001173,1.9512607510000635,3.6601821269996435,3.5060068769998907,18.59408088300006,17.683226675000697,9.039128505000008,10.217917630000102,2.775224210000033,2.2288163759999406,36.32114201799959,2.4672143759999017,2.172327208999832,3.9844095020002896,4.4796542100002625,5.295270335999703,4.774724794000122,2.1118484589997024,3.0238052519998746,24.834575010000208,2.255074209999748,2.8592984189999697,9.866384046000348,3.070801416999984,4.268878627000049,1.4396263759999783,1.824437751000005,2.9577533760002552,3.214500917999885,1.9725501259999874,3.065116918000058,2.049019418000171,2.2502992509998876],"input_tokens":[231,3376,3301,196,244,3359,3078,412,3470,167,3687,128,3120,259,3224,3278,3288,3220,3418,3182,3502,198,225,174,545,3356,3092,264,3280,3086,3231,3368,129,3557,3272,3475,478,3150,3253,151,3007,3268,3152,3196,3352,3341,3307,3409,3323,3192],"output_tokens":[373,64,58,38,289,61,64,408,73,373,73,371,65,314,115,68,59,87,83,76,105,263,281,295,368,98,90,465,124,91,214,98,276,142,100,77,502,93,90,466,107,110,66,81,93,92,81,72,80,75]}}},
            {"model": r'$SPARQL-LLM_{sm}$', "results": {"DBpedia (EN)":{"llm_time":[4.999019502000003,4.625338127000006,3.683028168000007,11.740429087999985,1.259180791999995,2.348378209999993,23.23492426099999,1.5514382510000075,1.67836254300002,16.68661529999997,1.5194647510000152,1.2674002499999801,1.4201433759999986,1.356986667000001,1.041725458000002,1.4336225419999948,1.448758708999975,1.6015443750000031,1.4329080839999904,1.338803624999997,1.6464885010000216,1.945683416999998,2.972429168000019,6.844679546000009,2.4201575429999878,1.5848150010000097,3.2818895020000127,1.7410692499999811,2.4298322509999934,1.7566283340000268,2.0489116259999776,1.7768421679999733,2.0849055850000013,6.825264086000061,2.4270615009999688,2.304795667999997,3.861234419000027,2.3868684600000165,2.2359282919999828,2.747049627000024,2.250973833000046,2.553689210000016,3.65693358499999,3.352916002000029,2.6474815430000262,3.193213291999996,4.639003835999972,4.471007336000014,4.1623184599999945,4.123062461000018,3.8668985020000264,3.4814880440000024,8.127916460999927,1.3239731259999985,1.4818166670000323,2.65008883400003,1.3710229590000154,1.373400791999984,5.099198836000028,1.5280548759999988,1.8337604590000183,1.2997182510000016,19.999008342999957,6.5835479620000115,1.4585333759999912,2.3714225840000154,1.5835116670000389,1.350328543000046,1.6597838330000059,2.0967305010000246,17.63373721699986,2.216078875999983,2.337893751000024,2.5273867099999734,2.7013885430000073,3.0886886269998968,3.8292307099999334,4.377508710000029,5.241621210999938,5.314331834999962,6.459861294999996,13.43951442399998,15.782200549000208,1.123672082999974,4.785193669000023,1.1133703749999313,15.600095382999939,1.518827291999969,1.525182792999999,1.7999478749999298,1.7625724179999906,15.9772081320001,2.3585066260000076,2.6445425839999643,19.476894340999934,4.917956918999948,18.463616217000094,7.986482626999987,4.832828336000034],"input_tokens":[5204,5633,5143,183,5648,5077,1121,5391,4733,1382,5078,5855,5367,5207,5297,5049,5377,5423,5283,4967,5378,5435,5277,166,5324,5585,179,5247,5297,5211,5424,5699,5401,548,5460,5204,5046,5464,5234,5296,5365,5813,5604,5416,5402,5245,5647,5236,5386,5465,5145,5358,180,4981,5264,5426,5268,5050,200,5619,5388,5546,284,182,5065,4986,5190,5400,5191,5341,186,5072,5640,5410,5424,5206,5675,4917,5585,5166,5202,213,315,5282,139,5182,347,5392,4542,5350,5602,749,5569,5629,524,5180,183,220,5252],"output_tokens":[75,93,53,54,58,108,242,55,52,193,67,53,68,60,47,47,86,93,50,81,66,106,97,168,91,53,14,63,62,54,53,56,95,33,84,74,49,98,69,116,71,116,122,70,51,78,113,83,61,63,84,82,162,54,47,110,70,62,103,71,93,55,314,140,52,86,61,49,50,55,237,54,51,53,40,60,82,53,86,74,139,34,171,50,145,52,162,95,74,94,74,344,90,56,232,90,157,14,108]},"DBpedia (ES)":{"llm_time":[4.511754918999998,4.773322709999995,3.1959137099999992,11.235522212999996,1.3128057919999918,8.745075129,12.133981880999983,1.406494667000004,1.789959250999999,1.720278293000007,1.7622900419999894,1.4957419169999753,1.4426886249999882,1.607713667000013,1.0394108760000051,1.1356861680000065,1.5317393760000186,2.034919959000007,1.2363307920000182,1.6880266260000099,1.3956349999999986,1.457484542000003,1.7857693340000083,2.246378542000002,3.1412748770000007,1.8123308339999937,1.871847583999994,2.018311959000016,2.269667085000009,3.073044710000005,1.5210952929999735,1.7080336249999846,2.4067394589999935,7.163832169999978,2.69596287600001,2.939793000999998,1.8871168759999932,2.6834497930000225,16.85122659199999,4.238310044000002,2.2273276679999867,4.246442627000022,3.1422057099999847,3.1851065019999965,2.7842093760000353,3.5285500429999956,4.453781542999991,4.814789793999978,4.0772545849999915,3.5122263769999904,3.3697962509999684,3.7838753350000047,18.042787635000025,2.4014420429999745,1.1238099999999918,1.7079364170000417,1.4600235419999876,1.2232665419999762,4.198422085000004,1.771014000999969,1.5977794169999697,1.356159918000003,12.841497422000032,6.528205836999973,1.5332176260000097,1.2972660010000254,1.3899926259999802,1.4879491259999895,1.9289112919999525,2.05565245899993,18.806472509000173,2.2129313339999044,2.1743376679999074,2.5448793340000293,2.776205875999949,3.171587918,4.234974168999997,4.347606752000047,5.336138211000048,29.83626742900003,5.804322501999991,11.866968964999842,7.0543752950001135,1.11838258399996,23.71742513599986,1.2653728340000043,13.2025610070001,1.9115495009999677,1.680339000999993,1.9224109179999687,1.9381300009999904,19.83660984200003,3.247393751000004,2.6470051260000673,4.884401709999906,5.373806836000085,19.66483792500003,7.747304087999851,4.540970752000021],"input_tokens":[5253,5521,5089,189,5634,5125,345,5332,4736,5704,5037,5855,5290,5160,5312,5049,5378,5424,5338,4962,5336,5417,5252,5014,5250,5489,5023,5219,5386,5198,5282,5622,5394,554,5479,5243,5114,5386,200,5317,5367,5783,5528,5412,5403,5149,5606,5203,5386,5466,5132,5386,212,5057,5250,5349,5074,5028,212,5608,5367,5550,229,215,4914,5171,5237,5356,5253,5386,252,4999,5683,5453,5415,5332,5613,4899,5592,541,5274,216,190,5221,1680,5186,187,5365,4545,5329,5558,791,5548,5607,5453,5185,185,221,5256],"output_tokens":[75,89,53,70,58,110,110,55,53,110,90,53,66,60,47,48,86,93,50,81,66,69,97,90,87,53,53,68,62,62,52,57,94,37,81,113,49,98,163,116,69,116,87,70,51,80,113,83,62,63,84,83,164,91,48,110,70,62,16,71,90,56,237,27,60,69,61,49,51,55,184,54,48,52,40,60,97,53,83,301,123,49,71,50,238,52,199,94,73,122,74,235,92,57,93,90,165,16,108]},"Corporate":{"llm_time":[15.229531048000013,1.7840942930000665,1.8361201259999689,12.485797881000053,11.252750255000024,9.522846088000165,1.2605722929999956,13.701300839000169,2.1763698760000807,16.18143729899998,13.905417672999874,1.2743482500000027,1.356968168000094,7.276187003999894,1.4509963339999103,1.0437857930000973,1.2229498760000297,13.575392797000177,1.3083931679998386,1.5499740010000096,1.6774942090000877,11.903491589000168,20.54246746700005,18.31670459100019,12.835682130999885,19.93736484499982,1.828408958999944,20.562330093000128,2.409521500999972,1.8460034590000305,1.7792818340001304,1.8061361679999663,17.16291417399998,1.9217354590000468,1.7169480420000127,1.3945593339999505,22.2932226370001,2.28602816800003,1.7428130840000904,23.320185219000223,3.3696918349999123,2.250450125000043,1.7394320429998515,2.1211340849999942,2.1600178759999835,2.1322057509999013,2.143601335000085,19.165685839999924,3.8792134600000736,4.353232169000194],"input_tokens":[363,3376,3301,378,376,345,3078,377,3470,419,361,3407,3120,141,3224,3278,3288,579,3418,3182,3502,276,260,484,852,665,3092,347,3280,3086,3231,3368,318,3557,3272,3475,502,3150,3253,370,3007,3268,3152,3196,3352,3341,3307,396,3323,3192],"output_tokens":[275,67,60,153,180,179,79,182,77,235,168,58,64,238,103,60,60,300,84,92,96,168,238,210,318,245,91,212,102,73,87,101,214,88,93,76,298,102,90,237,165,109,76,106,105,88,70,261,84,76]}}},
            {"model": r'$SPARQL-LLM_{os}$', "results": {"DBpedia (EN)":{"llm_time":[2.875806252000075,5.938265878000038,4.37628508600028,2.932047083999805,11.918107421999593,5.437334626000393,31.847182099000293,4.189832044000013,2.344031126000118,3.910465710999688,1.9153776680000192,7.301750544999777,13.903366755999741,2.9554342100000213,6.970800337000128,4.753646293000202,6.036955837000278,5.347169626999857,2.7048447930001203,17.686144715999944,3.6861314189995937,5.210168668999813,24.016411344000062,20.09040917500033,11.435852589000206,2.0660822930003633,40.117001642000105,8.715520670999922,5.117937209000047,9.371821628999896,20.91934571799993,6.861955545000001,2.6495431680004913,16.998517299000014,22.502360634999604,23.454647009999462,6.5704816699999355,4.917832211000132,95.74947917000009,7.760530753999774,5.048947794000014,85.54730137299975,4.63529975199981,47.38322435600003,18.6631375930001,3.7537852519999433,16.184772757000246,5.6751585450001585,9.492768753999371,5.0315084599997135,6.055439003000174,6.394422545000452,4.845216585999879,75.47026453299986,14.509343549000732,6.16366308600027,4.144572252000216,24.02299759499965,5.468457252999542,4.884908085999996,11.269219129000703,7.578314420999959,65.74424107100003,43.23441689500123,12.58287050599938,4.8552073770006245,2.0381454170001234,3.7302178349991664,3.660796417999336,4.464852209999663,84.38183008000033,4.1544328769996355,5.739259294000476,3.548256252000101,6.556961211000271,4.079384210000171,17.499485381999875,3.646722377000515,24.59443638599987,3.3212130430001707,5.439128753000659,45.81058043700068,77.88861099299811,4.158647960000053,3.9308291269999245,24.00060551000024,8.26523150400044,7.457789420000154,10.83973442200022,7.308255586999621,6.950069545000588,68.3440075719991,25.645358970001325,103.11309250400063,6.181575044000056,1.1858901260002312,16.441983924999477,16.95526900599998,4.572283252000489],"input_tokens":[5266,5695,5205,5615,417,5139,365,5453,4795,5751,5140,5917,5429,5271,5359,5111,5439,5485,5345,5029,5440,5497,5339,5084,5386,5649,371,5309,5359,5273,5486,5761,5463,5609,5522,281,5108,5526,2383,5358,5427,291,5666,402,306,5307,5709,5298,5448,5527,5207,5420,5549,1224,5326,5488,5330,5112,5632,5681,5450,5608,446,376,5127,5048,5252,5462,5253,5403,248,5134,5702,5472,5486,5268,5737,4979,288,5228,5264,416,435,5344,5183,248,5530,5454,4604,5412,5664,727,352,379,5512,5242,364,324,5314],"output_tokens":[351,408,172,531,116,305,464,199,194,395,512,209,328,314,221,143,330,354,167,433,279,295,535,698,214,229,66,315,314,209,380,299,289,936,1376,827,337,294,2300,412,245,1145,233,1158,138,358,842,304,295,220,271,338,449,1405,162,288,375,442,566,249,317,399,1408,411,238,233,230,150,171,241,1821,240,168,205,373,166,357,173,877,335,398,872,1144,222,230,1267,211,376,709,462,374,1415,261,2328,284,220,842,82,468]},"DBpedia (ES)":{"llm_time":[3.579767666999942,2.9463184180003736,1.662852251000004,91.66738737499963,51.27846864799949,5.252588794000076,35.517281681999975,2.832278876000146,13.67247383899985,14.877045672999884,7.4687471279999045,4.44941212699996,1.7235200840000289,9.661925672000052,3.1458857519996855,9.407784545999675,7.8479444200002035,14.544294048999745,2.4526490010002817,5.044361793999997,4.537315002000014,2.0629894589997093,4.915973877999932,16.7622894240003,2.381837625999651,1.1727615839999999,9.381651044999671,6.268177294999987,1.6435846680001305,5.150663126999916,4.246535335999852,97.84153037799933,4.448197378000259,41.15109843599839,11.307228296000176,5.660166252999261,7.241062377999697,8.194294586999604,79.98479016099918,8.26606142000037,6.060816127999715,66.92910819700046,4.201851378000356,5.30798387699997,27.717543388000195,12.256446672000493,8.046427003000645,6.157634336999763,6.690253543999461,5.718272461000197,6.112582961000044,10.17122917100005,2.3297858349997114,58.034500526000556,5.658096295000178,12.379289380000046,7.260680377999961,11.581569922000199,11.065563463999752,6.529147086999728,15.512801799000044,4.29609287599942,4.140009710000413,47.20373235399893,6.71266475199991,1.2881897919996845,9.233926920999693,28.28901697099991,2.584982709000542,2.3559545010002694,72.73387653399914,38.43154710100134,4.7028340020006,3.653677252000307,10.564537670999925,16.965677592000247,7.7426126290001775,5.356511127999511,4.119301501999871,3.5570400850001533,10.591789589000655,44.74904702100048,83.58096812199892,5.145088835999559,5.523405169000398,5.954876252999384,4.863927086000331,5.8586217530000795,9.643863503999455,8.871614296000189,4.867796251999607,72.51404365799954,27.87070126299932,82.11331912300102,3.586305543999515,2.1837410839998483,54.1206331479998,7.855748754001979,2.682749585000238],"input_tokens":[5315,5583,5151,223,264,5187,294,5394,4798,5766,5099,5917,5337,5222,5374,5111,5440,5486,5400,5024,5398,5481,5316,5076,5312,5551,251,5281,5433,5260,5344,493,5456,470,5541,5305,5176,5448,291,5379,5429,579,5590,5474,220,5211,5668,5265,5448,5528,5194,5448,5557,1093,5312,5411,5136,5090,5606,5670,5429,5612,5592,381,4976,5233,5299,5418,5300,5450,382,441,5745,5515,5477,5394,5675,4961,5656,5129,5336,276,296,5283,5281,5248,5482,5427,4607,5391,5607,1160,285,594,5515,5247,398,427,5318],"output_tokens":[375,255,286,986,422,423,655,309,256,321,530,206,323,398,192,184,260,333,302,320,352,284,680,854,257,246,189,375,233,260,385,1773,219,463,638,338,400,479,743,463,322,1129,313,286,879,489,467,328,260,260,294,299,353,1118,275,360,373,490,390,352,462,209,408,558,227,329,420,234,506,277,1306,1015,267,283,330,176,438,235,361,497,315,878,1855,302,305,319,265,334,502,510,439,1076,393,1805,547,282,1340,136,304]},"Corporate":{"llm_time":[39.40744376699968,2.572943959999975,4.986896710999645,7.331008293998821,45.2228816450006,5.076527168999746,6.125463252999907,18.84290075900026,2.196023043000423,1.8746635419993254,4.616129877999811,3.1327570430003107,2.7567075420001856,38.029616807998536,9.677389045999917,1.5300696260001132,1.6531484170000112,2.2779448760002197,4.899355376999665,3.798552960000052,31.738989722999577,36.88343130799967,64.90594311300083,12.702547713999593,3.510645084999851,5.255059002000053,6.903690586999801,99.77358500299852,4.064688627000578,14.691593756999282,7.264261794000049,9.949894920999213,12.711524047001149,5.053646377000405,17.02299134200075,1.4866837090012268,22.353453218998766,37.97535639200032,3.449755751000339,37.34312635099923,7.183831962000113,10.021997671001373,3.970148585000061,91.55061537499932,9.106339920001119,7.004936795001413,1.7995955839996896,10.764185963000273,5.689541502000793,3.94971229300063],"input_tokens":[927,3440,3363,271,348,3421,3140,616,3532,3380,3749,3469,3182,1063,3286,3342,3335,3282,3480,3244,1683,347,365,3498,3510,3418,3154,635,3344,3148,3293,3430,262,3619,3334,3537,394,3212,3315,348,3069,3330,3214,1200,3414,3403,3354,3471,3385,3256],"output_tokens":[979,333,402,655,672,328,364,1405,272,307,412,250,222,364,790,176,395,359,428,470,1069,949,838,445,458,540,832,1606,588,401,641,870,1015,647,622,348,978,697,405,748,560,453,243,1262,334,374,461,311,343,363]}}},
        ]
    )

    sota_time_results = pd.DataFrame(
        [
            {"dataset": "DBpedia (EN)", "time": pd.read_sql_query("SELECT * from responses", sqlite3.connect(os.path.join("data", "benchmarks", "TEXT2SPARQL", "queries", "infai_db25_responses.db"))).iloc[::2]['time'].apply(lambda x: pd.to_datetime(x)).diff().dt.total_seconds().median()},
            {"dataset": "Corporate", "time": pd.read_sql_query("SELECT * from responses", sqlite3.connect(os.path.join("data", "benchmarks", "TEXT2SPARQL", "queries", "infai_ck25_responses.db")))['time'].apply(lambda x: pd.to_datetime(x)).diff().dt.total_seconds().median()},
        ]
    )

    bio_results = pd.DataFrame(
        [
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Uniprot", "F1 Score": 0.5046329201631791},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Uniprot", "F1 Score": 0.20724562165291652},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Uniprot", "F1 Score": 0.5288815526210484},

            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Cellosaurus", "F1 Score": 0.416005291005291},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Cellosaurus", "F1 Score": 0.6583108413466117},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Cellosaurus", "F1 Score": 0.26593791722296395},

            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Bgee", "F1 Score": 0.6449450109027868},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Bgee", "F1 Score": 0.5799191959664763},
            {"model": r'$SPARQL-LLM_{lg}$', "dataset": "Bgee", "F1 Score": 0.6700231481481482},


            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Uniprot", "F1 Score": 0.22087355701705125},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Uniprot", "F1 Score": 0.1678154406827896},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Uniprot", "F1 Score": 0.24755357189955668},

            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Cellosaurus", "F1 Score": 0.13789690263794535},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Cellosaurus", "F1 Score": 0.2298300138639789},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Cellosaurus", "F1 Score": 0.18089079859227641},

            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Bgee", "F1 Score": 0.30666666666666664},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Bgee", "F1 Score": 0.5522089008509367},
            {"model": r'$SPARQL-LLM_{sm}$', "dataset": "Bgee", "F1 Score": 0.21011904761904762},


            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Uniprot", "F1 Score": 0.22900697394733113},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Uniprot", "F1 Score": 0.16666666666666666},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Uniprot", "F1 Score": 0.2543672014260249},

            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Cellosaurus", "F1 Score": 0.42693432229968886},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Cellosaurus", "F1 Score": 0.21873586906089693},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Cellosaurus", "F1 Score": 0.4882152273822735},

            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Bgee", "F1 Score": 0.31666666666666665},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Bgee", "F1 Score": 0.2647058823529412},
            {"model": r'$SPARQL-LLM_{os}$', "dataset": "Bgee", "F1 Score": 0.2647058823529412},
        ]
    )

    plot_hyperparameter_tuning_results(proportion_results=proportion_results,
                                       embeddings_results=embeddings_results,
                                       examples_results=examples_results,
                                       ablation_results=ablation_results,
                                       baseline_results=baseline_results,
                                       model_results=model_results,
                                       save_plot=False,
                                    )

    plot_overall_results(overall_results=overall_results,
                         sota_results=sota_results,
                         save_plot=False,
                        )
    
    plot_cost_analysis_results(cost_results=cost_results,
                               sota_time_results=sota_time_results,
                               save_plot=False,
                            )

    plot_bio_results(bio_results=bio_results,
                     save_plot=False,
                    )
