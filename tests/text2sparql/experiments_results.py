import os
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
    
    sns.set_theme(context="paper", style="white", color_codes=True, font_scale=3.5)
    fig = plt.figure(figsize=(30, 15))
    gs = GridSpec(2, 6, figure=fig)

    ax = [fig.add_subplot(gs[0, 0:2]), 
          fig.add_subplot(gs[0, 2:4]), 
          fig.add_subplot(gs[0, 4:6]), 
          fig.add_subplot(gs[1, 1:3]),
          fig.add_subplot(gs[1, 3:5]),
        ]

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

    ax[0].set_title("(i) Proportion of Provided Schema", fontweight="bold")
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
    
    ax[1].set_title("(ii) Embeddings Model", fontweight="bold")
    ax[1].set_xlim(0, .75)
    ax[1].set_xticks([.1, .2, .3, .4, .5, .6, .7], [".1", ".2", ".3", ".4", ".5", ".6", ".7"])
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

    ax[2].set_title("(iii) Number of Provided Examples", fontweight="bold")
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

    ax[3].set_title("(iv) Large Language Model", fontweight="bold")
    ax[3].set_xlim(0, .75)
    ax[3].set_xticks([.1, .2, .3, .4, .5, .6, .7], [".1", ".2", ".3", ".4", ".5", ".6", ".7"])
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

    ax[4].set_title("(v) Ablation Study", fontweight="bold")
    ax[4].set_xlim(0, .75)
    ax[4].set_xticks([.1, .2, .3, .4, .5, .6, .7], [".1", ".2", ".3", ".4", ".5", ".6", ".7"])
    ax[4].set_ylabel("")
    ax[4].get_legend().remove()


    fig.legend(*ax[1].get_legend_handles_labels(), bbox_to_anchor=(0.5, 1.1), loc='upper center', ncol=4, title="TEXT2SPARQL Corpus")
    sns.despine(top=True, right=True)
    plt.tight_layout()

    if save_plot:
        plt.savefig(os.path.join("data", "benchmarks", f"{time.strftime('%Y%m%d_%H%M')}_hyperparameter_tuning.png"), bbox_inches="tight")
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
            {"model": "Gemini 1.5 Pro", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "Gemini 1.5 Pro", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "Gemini 1.5 Pro", "dataset": "DBpedia (EN)", "F1 Score": 0},

            {"model": "Gemini 1.5 Pro", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "Gemini 1.5 Pro", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "Gemini 1.5 Pro", "dataset": "DBpedia (ES)", "F1 Score": 0},

            {"model": "Gemini 1.5 Pro", "dataset": "Corporate", "F1 Score": 0},
            {"model": "Gemini 1.5 Pro", "dataset": "Corporate", "F1 Score": 0},
            {"model": "Gemini 1.5 Pro", "dataset": "Corporate", "F1 Score": 0},


            {"model": "Mistral Large 2", "dataset": "DBpedia (EN)", "F1 Score": 0.637605319694327},
            {"model": "Mistral Large 2", "dataset": "DBpedia (EN)", "F1 Score": 0.6047127951770502},
            {"model": "Mistral Large 2", "dataset": "DBpedia (EN)", "F1 Score": 0.6249292195575908},

            {"model": "Mistral Large 2", "dataset": "DBpedia (ES)", "F1 Score": 0.6446008219830448},
            {"model": "Mistral Large 2", "dataset": "DBpedia (ES)", "F1 Score": 0.612939791184551},
            {"model": "Mistral Large 2", "dataset": "DBpedia (ES)", "F1 Score": 0.6507461671408128},

            {"model": "Mistral Large 2", "dataset": "Corporate", "F1 Score": 0.3397032907136823},
            {"model": "Mistral Large 2", "dataset": "Corporate", "F1 Score": 0.34743064109986266},
            {"model": "Mistral Large 2", "dataset": "Corporate", "F1 Score": 0.3212811489748454},


            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (EN)", "F1 Score": 0},

            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "Claude 3.5 Sonnet", "dataset": "DBpedia (ES)", "F1 Score": 0},

            {"model": "Claude 3.5 Sonnet", "dataset": "Corporate", "F1 Score": 0},
            {"model": "Claude 3.5 Sonnet", "dataset": "Corporate", "F1 Score": 0},
            {"model": "Claude 3.5 Sonnet", "dataset": "Corporate", "F1 Score": 0},


            {"model": "GPT-4.1", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "GPT-4.1", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "GPT-4.1", "dataset": "DBpedia (EN)", "F1 Score": 0},

            {"model": "GPT-4.1", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "GPT-4.1", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "GPT-4.1", "dataset": "DBpedia (ES)", "F1 Score": 0},

            {"model": "GPT-4.1", "dataset": "Corporate", "F1 Score": 0},
            {"model": "GPT-4.1", "dataset": "Corporate", "F1 Score": 0},
            {"model": "GPT-4.1", "dataset": "Corporate", "F1 Score": 0},


            {"model": "GPT-4o", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "GPT-4o", "dataset": "DBpedia (EN)", "F1 Score": 0},
            {"model": "GPT-4o", "dataset": "DBpedia (EN)", "F1 Score": 0},

            {"model": "GPT-4o", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "GPT-4o", "dataset": "DBpedia (ES)", "F1 Score": 0},
            {"model": "GPT-4o", "dataset": "DBpedia (ES)", "F1 Score": 0},

            {"model": "GPT-4o", "dataset": "Corporate", "F1 Score": 0},
            {"model": "GPT-4o", "dataset": "Corporate", "F1 Score": 0},
            {"model": "GPT-4o", "dataset": "Corporate", "F1 Score": 0},
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