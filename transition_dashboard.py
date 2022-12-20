from collections import defaultdict
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import logging

# import my stuff.
import jira_transistions as jtrans

logging.basicConfig(level=logging.INFO)

# side bar: pick life cycle
lifecycles = {}
lifecycles["estimating"] = jtrans.estimating
lifecycles["approved_waiting"] = jtrans.approved_waiting

# get data (save snapshots for this session?)
if "current_snapshots" not in st.session_state:
    st.session_state["current_snapshots"] = defaultdict(lambda: defaultdict(dict))

current_snapshots = st.session_state["current_snapshots"]


# some helper functions
def chart_count_sum(df):
    with col1:
        st.write("Aging Analyis")
        st.bar_chart(df["Count"])

    with col2:
        st.write("Value by Age")
        st.bar_chart(df["SumVal"])


def list_jira_filter_url(jira_filter):
    jira_base_url = "https://thebrightlink.atlassian.net/issues/?jql=filter%3D"
    return jira_base_url + jira_filter


# layout config
st.set_page_config(
    page_title="TSP pipeline",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="auto",
)

# . Side bar
st.sidebar.title("Brightlink Project Pipeline")

lifecycle_name = st.sidebar.selectbox("Lifecycle:", lifecycles.keys())
lifecycle = lifecycles[lifecycle_name]
jira_filter = st.sidebar.selectbox("Filter", lifecycle["jira_filters"])

st.sidebar.write(f"Jira links for {lifecycle_name}:")
for j_filter in lifecycle["jira_filters"]:
    st.sidebar.write(f"[{j_filter}]({list_jira_filter_url(j_filter)})")

if (
    lifecycle_name in current_snapshots
    and jira_filter in current_snapshots[lifecycle_name]
):
    logging.info(f"found data for {lifecycle_name}/{jira_filter}")
    snap_shot = current_snapshots[lifecycle_name][jira_filter]
    all_raw_data = current_snapshots["all_raw_data"]
else:
    logging.info(f"getting data for {lifecycle_name}/{jira_filter}")
    with st.spinner(f"getting data for {lifecycle_name}/{jira_filter}"):
        current_snapshots[lifecycle_name][jira_filter] = jtrans.get_snapshot(
            lifecycle, jira_filter
        )
    snap_shot = current_snapshots[lifecycle_name][jira_filter]

    # Add raw data to the all raw data if it's new
    new_raw_data = snap_shot["sshot_raw"]
    # all_raw_data = current_snapshots.get('all_raw_data')

    if "all_raw_data" not in current_snapshots:
        logging.info("Creating all raw data the first time")
        current_snapshots["all_raw_data"] = snap_shot["sshot_raw"]
    else:
        logging.info("appending new rawdata")
        current_snapshots["all_raw_data"] = pd.concat(
            [current_snapshots["all_raw_data"], new_raw_data], axis=0, join='outer'
        ).reset_index(drop=True)

    all_raw_data = current_snapshots["all_raw_data"]

# desc.aging. estimate in columns
st.title(f"Project Lifecyle: {lifecycle_name}")
# st.write(snap_shot.keys())
aging = snap_shot["aging_dist"]
client_estimate_dist = snap_shot["client_estimate_dist"]
sshot_description = snap_shot["sshot_description"]
filtered_descriptions = sshot_description.filter(regex="age$")
filtered_descriptions["client_estimate"] = sshot_description["client_estimate"]
raw_data = snap_shot["sshot_raw"]

with st.expander("The Basics table..."):
    st.write(filtered_descriptions)

st.header("Aging Distribution")
col1, col2, col3 = st.columns(3)
chart_count_sum(aging)
with col3:
    st.write(aging[["Count", "SumVal", "AvgVal"]])

st.header("Estimate Distribution")
col1, col2, col3 = st.columns(3)
chart_count_sum(client_estimate_dist)
with col3:
    st.write(client_estimate_dist[["Count", "SumVal", "AvgVal"]])

# box chart of filters for comparison
# box_chart_df=
# aging_boxplot = all_raw_data.boxplot(column=["client_estimate"], by="phase_code")
fig, ax = plt.subplots()
all_raw_data.boxplot(
    column=["client_estimate"], by="jira_filter", ax=ax, patch_artist=True
)
plt.rc("font", size=8)
plt.title("Box plot of client esimate by jira filter")
plt.xlabel("Jira filter")
plt.ylabel("Estimate Value in USD")
plt.xticks(rotation=75)

st.write("Box Plot")
st.pyplot(fig)

# full list of items pick from LC/filter
st.write("All Records")
st.write(all_raw_data)
