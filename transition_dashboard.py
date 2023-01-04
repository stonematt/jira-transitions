from collections import defaultdict
import streamlit as st
import pandas as pd
import plotly.express as px
import logging

# import my stuff.
import jira_transistions as jtrans

logging.basicConfig(level=logging.INFO)

# side bar: pick life cycle
lifecycles = {}
lifecycles["estimating"] = jtrans.estimating
lifecycles["pending_approval"] = jtrans.pending_approval
lifecycles["approved_waiting"] = jtrans.approved_waiting
lifecycles["in_flight"] = jtrans.in_flight
lifecycles["approved_in_flight"] = jtrans.approved_in_flight
lifecycles["recently_completed"] = jtrans.recently_completed

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


def df_boxplot(df, data_column, color_by, group_by="", title="", xlabel="", ylabel=""):
    """render a px.box plot with standardized formatting

    Args:
        df (dataframe): _description_
        data_column (df column): series with numeric values
        colorby (df column): series to color boxes by
        group_by (df column): series to group values by
        title (str, optional): title of chart. Defaults to "".
        xlabel (str, optional): x axis label. Defaults to "".
        ylabel (str, optional): y axis label. Defaults to "".
    """
    title = data_column if not title else title
    xlabel = group_by if not xlabel else xlabel

    fig = px.box(
        df,
        x=data_column,
        color=color_by,
        y=group_by,
        points="all",
        title=title,
        hover_name="key",
        hover_data=["client", "key", "summary"],
    ).update_layout(
        yaxis_title=ylabel,
        xaxis=dict(
            showgrid=True,
            zeroline=True,
            zerolinewidth=2,
        ),
        xaxis_title=xlabel,
        legend_orientation="h",
        legend_groupclick="togglegroup",
        height=600,
    )

    st.plotly_chart(fig, theme="streamlit")


def get_jira_url(key):
    return f"https://thebrightlink.atlassian.net/browse/{key}"


def df_to_histogram(df, data_column, group_by, sum_column=None):
    if sum_column:
        counts = (
            df.groupby([group_by, data_column])[sum_column]
            .sum()
            .reset_index(name="Sum")
        )
    else:
        counts = df.groupby([group_by, data_column]).size().reset_index(name="Count")
    counts_pivot = counts.pivot_table(
        index=data_column, columns=group_by, values=counts.columns[2]
    )
    return counts_pivot


# make a bar chart of aging using px
def grouped_bar_chart(df, title="", y_title=""):
    fig = px.bar(df, barmode="group", title=title).update_layout(
        yaxis_title=y_title,
        legend_orientation="h",
        legend_groupclick="togglegroup",
        legend_itemclick="toggle",
    )
    st.plotly_chart(fig, theme="streamlit")


def to_comma(x):
    return "{:,.0f}".format(x)


def quick_df_summary(df, group_by, data_column, percentile=0.85):
    """Create a dataframe with count of rows and median value of a data column

    Args:
        df (dataframe): data frame of raw data
        group_by (str): name of column to group by
        data_column (str): name of column to caculate values for

    Returns:
        dataframe: Dataframe of results
    """
    grouped_df = df.groupby(group_by)
    count = grouped_df["key"].count()
    median = grouped_df[data_column].median()
    total = grouped_df[data_column].sum()

    # calculate the sum of the key below the percentile
    sum_below_percentile = grouped_df[data_column].apply(
        lambda x: x[x < x.quantile(percentile)].sum()
    )

    results_df = pd.DataFrame(
        {
            "count": count,
            "median": median,
            "total": total,
            f"sum_below_{percentile*100}-tile": sum_below_percentile,
        }
    ).reset_index()
    results_df["median"] = results_df["median"].map(to_comma)
    results_df["total"] = results_df["total"].map(to_comma)
    results_df[f"sum_below_{percentile*100}-tile"] = results_df[
        f"sum_below_{percentile*100}-tile"
    ].map(to_comma)
    return results_df


# layout config
st.set_page_config(
    page_title="TSP pipeline",
    page_icon="random",
    layout="wide",
    initial_sidebar_state="auto",
)

# . Side bar
st.sidebar.title("Brightlink Project Pipeline")

lifecycle_name = st.sidebar.selectbox("Lifecycle:", lifecycles.keys())
lifecycle = lifecycles[lifecycle_name]
jira_filter = st.sidebar.selectbox("Filter", lifecycle["jira_filters"])

age_baseline = st.sidebar.radio("Baseline for aging:", ("Phase Age", "Created"))
boxplot_age = "phase_age" if age_baseline == "Phase Age" else "total_age"

st.sidebar.write(f"\nGo to Jira {lifecycle_name}:")
for j_filter in lifecycle["jira_filters"]:
    st.sidebar.write(f"[{j_filter}]({list_jira_filter_url(j_filter)})")

if (
    lifecycle_name in current_snapshots
    and jira_filter in current_snapshots[lifecycle_name]
):
    logging.info(f"found data for {lifecycle_name}/{jira_filter}")
    snap_shot = current_snapshots[lifecycle_name][jira_filter]
    # all_raw_data_master = current_snapshots["all_raw_data"]
else:
    logging.info(f"getting data for {lifecycle_name}/{jira_filter}")
    with st.spinner(
        f"Go make a coffee, getting data for {lifecycle_name}/{jira_filter} may take a couple minutes"
    ):
        current_snapshots[lifecycle_name][jira_filter] = jtrans.get_snapshot(
            lifecycle, jira_filter
        )
    snap_shot = current_snapshots[lifecycle_name][jira_filter]

    # Add raw data to the all raw data if it's new
    new_raw_data = snap_shot["sshot_raw"]

    if "all_raw_data" not in current_snapshots:
        logging.info("Creating all raw data the first time")
        current_snapshots["all_raw_data"] = snap_shot["sshot_raw"]
    else:
        logging.info("appending new rawdata")
        current_snapshots["all_raw_data"] = pd.concat(
            [current_snapshots["all_raw_data"], new_raw_data], axis=0, join="outer"
        ).reset_index(drop=True)

all_raw_data_master = current_snapshots["all_raw_data"]
all_raw_data_master["URL"] = all_raw_data_master["key"].apply(get_jira_url)
all_raw_data = all_raw_data_master.copy()
# all_raw_data = all_raw_data_master

# overall filter of data in the dashboard:
col1, col2, col3 = st.columns([2, 1, 2])
with col1:
    # Create a multi-select widget for the billable_type column
    billable_type_options = all_raw_data_master["billable_type"].unique().tolist()
    billable_type_selection = st.multiselect(
        "Select billable types", billable_type_options, default=billable_type_options
    )

    # Filter the dataframe based on the selected billable types
    # if billable_type_selection:
    if billable_type_selection:
        all_raw_data = all_raw_data[
            all_raw_data["billable_type"].isin(billable_type_selection)
        ]
    else:
        all_raw_data = all_raw_data_master.copy()

with col2:
    # Create a dropdown menu for the client column
    client_options = ["All"] + sorted(all_raw_data_master["client"].unique().tolist())
    client_focus = st.selectbox("Focus on one client:", client_options)

    # Filter the dataframe based on the selected client
    if client_focus != "All":
        all_raw_data = all_raw_data[all_raw_data["client"] == client_focus]

with col3:
    # Create a dropdown menu for the jira filter
    jira_filter_options = ["All"] + sorted(
        all_raw_data_master["jira_filter"].unique().tolist()
    )
    jira_filter_focus = st.selectbox("Focus on one jira_filter:", jira_filter_options)

    # Filter the dataframe based on the selected jira filter
    if jira_filter_focus != "All":
        all_raw_data = all_raw_data[all_raw_data["jira_filter"] == jira_filter_focus]


# some data helpers.
all_age_hist = df_to_histogram(all_raw_data, "phase_age_bins", "jira_filter")
all_age_wt_hist = df_to_histogram(
    all_raw_data, "phase_age_bins", "jira_filter", sum_column="client_estimate"
)
all_estimate_hist = df_to_histogram(all_raw_data, "client_estimate_bins", "jira_filter")
all_estimate_wt_hist = df_to_histogram(
    all_raw_data, "client_estimate_bins", "jira_filter", sum_column="client_estimate"
)

tab1, tab2, tab3 = st.tabs(["Pipeline Summary", "Scatter Plot", "Filter Details"])

with tab3:  # details of lifecyle/filter
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

with tab2:
    fig = px.scatter(
        all_raw_data,
        size="total_age",
        y="client_estimate",
        x="phase_age",
        color="jira_filter",
        # symbol="phase_code",
        hover_name="key",
        hover_data=["client", "key", "summary"],
        title="Phase age v. Client Estimate (size is total age)",
    ).update_layout(
        height=700,
        legend_orientation="h",
        legend_groupclick="togglegroup",
        legend_itemclick="toggle",
    )
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)

    # full list of items pick from LC/filter
    st.write("All Records Retreived")

    st.dataframe(
        all_raw_data[
            [
                "key",
                "summary",
                "client",
                "client_estimate",
                "billable_type",
                "total_age",
                "current_status",
                "phase_age",
                "phase_age_bins",
                "phase_code",
                "jira_filter",
                "URL",
            ]
        ]
    )


with tab1:  # summary of downloaded data
    # box chart of filters for comparison
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        st.header("Aging Summary")
        st.write(
            quick_df_summary(all_raw_data, "jira_filter", boxplot_age)[
                ["jira_filter", "count", "median"]
            ]
        )

        df_boxplot(
            all_raw_data,
            boxplot_age,
            "jira_filter",
            "phase_code",
            "Box plot of age by jira filter",
            "Age in days",
        )

        grouped_bar_chart(all_age_hist, "Histogram of Age by Filter", "Count of issues")
        grouped_bar_chart(
            all_age_wt_hist,
            "Value of Projects by Age and Filter",
            "Sum of Client Estimate",
        )

    with col2:
        st.header("Revenue Estimate Summary")
        st.write(quick_df_summary(all_raw_data, "jira_filter", "client_estimate"))

        df_boxplot(
            all_raw_data,
            "client_estimate",
            "jira_filter",
            "phase_code",
            "Box plot of client estimate by jira filter",
            "Estimate Value in USD",
        )
        grouped_bar_chart(
            all_estimate_hist, "Histogram of Estimates by Filter", "Count of issues"
        )
        grouped_bar_chart(
            all_estimate_wt_hist,
            "Value of Projects by Size and Filter",
            "Sum of Client Estimate",
        )
