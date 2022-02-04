# %%
import pandas as pd
import json
import jira_in_out as jbget

# import matplotlib.pyplot as plt

jira_balances = jbget.jira_balances
datadir = jbget.datadir

# a place to put dataframes
histories = {}


# %%
def hist_to_pd(history_report):
    hist_pd = pd.DataFrame(history_report)

    # pd_hist = hist_to_pd(history)
    # print(pd_hist.describe)
    hist_pd["in_p_wk"] *= -1
    hist_pd["in_count"] *= -1
    hist_pd["date"] = pd.to_datetime(hist_pd["date"])

    return hist_pd


# %%


def chart_df(df, title):

    df.plot.line(
        x="date", y=["delta_p_wk", "in_p_wk", "out_p_wk"], title=title, grid=True
    )


def build_histories(jira_balances, print_hitory=False):
    for jb in jira_balances:
        jira_balance = jira_balances[jb]
        history = jbget.load_history_from_file(datadir + jira_balance["hist_file"])
        histories[jb] = hist_to_pd(history)

        if print_hitory:
            print(f"Recent data from {jira_balance['hist_file']}")
            print(json.dumps(history[-1], sort_keys=True, indent=2))
            # chart_df(histories[jb], jb)


# %%
def main():

    build_histories(jira_balances, print_hitory=True)


if __name__ == "__main__":
    main()


# %%
