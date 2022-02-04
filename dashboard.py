import streamlit as st
import pandas as pd
import jira_balance_analysis as jbal

jira_balances = jbal.jira_balances

jbal.build_histories(jbal.jira_balances)

# jbal.histories["approved"]


current_hist = st.selectbox("Pick a history", jbal.histories.keys())

df = jbal.histories[current_hist]
df_pwk = df[["date", "delta_p_wk", "in_p_wk", "out_p_wk"]]
df_pwk = df_pwk.rename(columns={"date": "index"}).set_index("index")
df_pwk.sort_values(by=["index"], ascending=False, inplace=True)

st.line_chart(df_pwk.loc["2021-12-31":])

st.write("Raw Data")
df_pwk

st.write("Simple descriptive statistics")
d = df_pwk.describe()
d
