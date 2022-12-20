import streamlit as st

import jira_transistions as jtrans
import logging
logging.basicConfig(level=logging.INFO)
from collections import defaultdict

# side bar: pick life cycle
lifecycles = defaultdict(lambda: defaultdict(dict))
lifecycles["estimating"] = jtrans.estimating
lifecycles["approved_waiting"] = jtrans.approved_waiting

# get data (all filters?)
current_snapshots =  defaultdict(lambda: defaultdict(dict)){
    "estimating": {
        "backlog_estimating_all": "my data"
    }
}


# save data so you only have to get it once
# main
# title

st.title("Brightlink Project Pipeline")

lifecycle_name = st.sidebar.selectbox("Lifecycle:", lifecycles.keys())
lifecycle = lifecycles[lifecycle_name]
jira_filter = st.sidebar.selectbox("Filter", lifecycle["jira_filters"])
# st.write(lifecycles[lifecycle])
# st.write(lifecycle)

if (lifecycle_name, jira_filter) in current_snapshots:
    snap_shot = current_snapshots[lifecycle_name][jira_filter]
    # st.write(f"need data for {lifecycle_name}/{jira_filter}")
else:
    st.write(f"getting data for {lifecycle_name}/{jira_filter}")
    st.write(lifecycle)
    current_snapshots[lifecycle_name][jira_filter] = jtrans.get_snapshot(
        lifecycle, jira_filter
    )
    st.write(current_snapshots)


# desc.aging. estimate in columns
# box chart of filters for comparison

# full list of items pick from LC/filter
