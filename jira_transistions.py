# %%
import json
import pandas as pd
import logging
import streamlit as st
import bl_jira as blj

from datetime import datetime

logging.basicConfig(level=logging.INFO)


datadir = "./data/"
examplesdir = "./examples/"


"""
 # get issues from filter
 # get transistions form chage log
 #      deal w/ multiple trans to same status
 # put in pd.dataframe,
 #      todo:calc date buckets for aging
 # make visualization (see streamlit dashboard)
"""


def _to_date(jira_date):
    """return datetime object of date from jira time string
    that looks like: 2021-10-05T14:12:44.872-0400
    """
    d = datetime.strptime(jira_date, "%Y-%m-%dT%H:%M:%S.%f%z")
    return d


def get_transistions_for_issues(jira_issues, status_list):
    """return dictionary of issues w/ status change information"""
    status_list = status_list
    issues = []
    total_issues = len(jira_issues)
    progress_count = st.empty()
    progress_bar = st.progress(0)
    progress = 0
    for i in jira_issues:
        progress += 1
        progress_count.text(f"{progress} of {total_issues}")
        progress_bar.progress(progress / total_issues)
        if progress % 20 == 0 or progress == len(jira_issues):
            print(f"{progress} issues processed")

        issue = {}

        issue["key"] = i["key"]
        issue["summary"] = i["fields"]["summary"]
        issue["client"] = i["fields"].get("customfield_12513", {}).get("value", None)
        issue["client_estimate"] = i["fields"]["customfield_14925"]
        issue["billable_type"] = (
            i.get("fields", {}).get("customfield_14922", {}).get("value", None)
        )
        issue["created"] = i["fields"]["created"]
        issue["current_status"] = i["fields"]["status"]["name"]
        # todo: targetdate

        change_log = get_status_changes_summary(
            blj.get_issue_changelog(i["key"]), status_list
        )
        issue.update(change_log)

        issues.append(issue)
    # pprint(issue
    progress_count.empty()
    progress_bar.empty()
    return issues


def get_status_changes_summary(issue_log, status_list):
    """return an transistions dict from an issue's log"""
    status_changes = {}
    for status in status_list:
        status_changes[status + "_name"] = status
        status_changes[status + "_first"] = ""
        status_changes[status + "_last"] = ""
        status_changes[status + "_transitions"] = 0

    for v in issue_log["values"]:
        for i in v["items"]:
            if i["field"] == "status" and i["toString"] in status_list:
                status_changes[i["toString"] + "_transitions"] += 1
                # set the first date
                if status_changes[i["toString"] + "_first"] == "":
                    status_changes[i["toString"] + "_first"] = v["created"]
                elif _to_date(v["created"]) < _to_date(
                    status_changes[i["toString"] + "_first"]
                ):
                    status_changes[i["toString"] + "_first"] = v["created"]

                # set the most recent date
                if status_changes[i["toString"] + "_last"] == "":
                    status_changes[i["toString"] + "_last"] = v["created"]
                elif _to_date(v["created"]) > _to_date(
                    status_changes[i["toString"] + "_last"]
                ):
                    status_changes[i["toString"] + "_last"] = v["created"]

    # export_json(status_changes, "./deleteme.json")
    return status_changes


def _generate_aging_names(lifecycle_phase):
    aging_start = lifecycle_phase["first_status"] + "_last"
    aging_name = lifecycle_phase["phase_code"] + "_age"
    aging_bins = aging_name + "_bins"

    return aging_start, aging_name, aging_bins


def issues_to_pandas(status_changes, lifecycle_phase):
    """Converts dictionary of status changes to pandas dataframe
    that includes aging and estimating bins

    Args:
        status_changes (dict): jira change log of status changes
        lifecycle_phase (dict): configuration of lifecycle. need keys for
                                 "first_status" and "phase_code"

    Returns:
        dataframe:  dataframe with age from phase start,
                    ammended with jira filter and lifecycle phase
    """
    # aging_start = lifecycle_phase["first_status"] + "_last"
    # aging_name = lifecycle_phase["phase_code"] + "_age"
    # aging_bins = aging_name + "_bins"

    aging_start, aging_name, aging_bins = _generate_aging_names(lifecycle_phase)

    sc = pd.DataFrame(status_changes)
    sc[aging_start] = pd.to_datetime(sc[aging_start], utc=True)
    sc["created"] = pd.to_datetime(sc["created"], utc=True)
    # todo: make other dates be dates

    sc[aging_name] = (
        (pd.Timestamp.now(tz="UTC") - sc[aging_start]).where(
            pd.notna(sc[aging_start]), pd.Timestamp.now(tz="UTC") - sc["created"]
        )
    ).dt.days
    sc["phase_age"] = sc[aging_name]
    sc["total_age"] = (pd.Timestamp.now(tz="UTC") - sc["created"]).dt.days
    # todo: calculate days remaining

    # set aging bins
    bins = [0, 7, 14, 30, 60, 90, 120, 1000]
    lables = ["07d", "14d", "30d", "60d", "90d", "120d", "very old"]
    sc[aging_bins] = pd.cut(sc[aging_name], bins=bins, labels=lables)
    sc["phase_age_bins"] = sc[aging_bins]

    # set estimate bins
    estbins = [0, 500, 1000, 2000, 5000, 10000, 20000, 1000000]
    estlables = [
        "<$500",
        "<$1,000",
        "<$2,000",
        "<$5,000",
        "<$10,000",
        "<$20,000",
        "More",
    ]
    sc["client_estimate_bins"] = pd.cut(
        sc["client_estimate"], bins=estbins, labels=estlables
    )

    # todo: age bins on days remaining from target date.
    return sc


def category_distribution(status_changes, column):
    """Show histogram and order value of work in phase

    Args:
        status_changes (dataframe): from issues_to_pandas()
        column (string): the column to calculate frequency distribution

    Returns:
        dataframe: aggregation grouped by named column
    """

    # print(f"\nTotaling: ${status_changes['client_estimate'].sum()}")

    return (
        status_changes.groupby(column)["client_estimate"]
        .agg(Count="size", SumVal="sum", AvgVal="mean")
        .round(2)
    )


def export_json(dict, file):
    """save a json dictionary to a file for later

    dict - json dictionary to save

    file - filename to save
    """
    try:
        with open(file, "w") as fp:
            json.dump(dict, fp, sort_keys=True, indent=2)
    except FileNotFoundError as nofile:
        print(f"File not found: {nofile}")
        print(f"Create {examplesdir} to cache the raw data")
        # raise nofile


def get_working_issues(status_list, jira_filter, source="jira"):
    """get issues to process.  supports call to jira or local cached version

    Args:
        status_list (list): list of jira statuses to collect transistion data for
        jira_filter (string): name of jira filter to retrieve
        source (str, optional): "jira" to go to jira or "local" to open local file. Defaults to "jira".

    Raises:
        nofile: if local file of cached issues not found

    Returns:
        dict: issues w/ status transition information
    """
    logging.info(
        f"get_working_issues: status_list {type(status_list)}, jira_filter: {jira_filter}"
    )
    w_issues_file = examplesdir + jira_filter + "_" + status_list["filename"]

    if source == "jira":
        w_jira_issues = blj.get_issues_from_filter(jira_filter)
        w_issues = get_transistions_for_issues(w_jira_issues, status_list["statuses"])
        export_json(w_issues, w_issues_file)

    if source == "local":
        try:
            w_issues = json.load(open(w_issues_file))
        except FileNotFoundError as nofile:
            print(f"File not found: {nofile}")
            raise nofile

    logging.info(f"get_working_issues: returning {len(w_issues)} issues")
    return w_issues


def _amend_df(issues_df, phase_code, jira_filter):
    """Data pipeline step add today's date and meta data prior to saving

    Args:
        issues_df (dataframe): dataframe to ammend
        phase_code ([type]): [description]
        jira_filter ([type]): [description]

    Return:
        dataframe
    """
    issues_df["Date"] = pd.Timestamp.now().date()
    issues_df["phase_code"] = phase_code
    issues_df["jira_filter"] = jira_filter

    return issues_df


def get_snapshot(lifecycle, jira_filter):
    """Get current data snapshot from jira for a lifecycle phase from a jira filter
    This is the content to send to metabase

    Args:
        lifecycle (dict): lifecycle phase in the jira sales pipeline
        jira_filter (string): name of a saved jira filter

    Returns:
        dict: collection of 3 dataframes with snapshot anylysis:
            df sshot_description: description of the snapshot
            df aging_dist: aging distrbution
            df client_estimate_dist: distribution of client estimates
    """

    aging_start, aging_name, aging_bins = _generate_aging_names(lifecycle)

    print(f"\n================\nFetching data from {jira_filter}")
    # use "local" or "jira" to indicate whether to actually hit the jira api.
    snap_shot = get_working_issues(lifecycle, jira_filter, "jira")
    snap_shot_dfs = {}

    # make relevant dataframes
    logging.info("get_snapshot: start making dataframes")
    sshot = issues_to_pandas(snap_shot, lifecycle)
    snap_shot_dfs["sshot_raw"] = sshot

    snap_shot_dfs["sshot_description"] = sshot.describe(
        percentiles=[0.25, 0.5, 0.8, 0.9]
    ).round(2)

    snap_shot_dfs["aging_dist"] = category_distribution(sshot, aging_bins)

    snap_shot_dfs["client_estimate_dist"] = category_distribution(
        sshot, "client_estimate_bins"
    )

    # add columns for todays date, phase, and jira filter for reporting
    # snap_shot_dfs = [sshot_description, aging_dist, client_estimate_dist]

    for key, df in snap_shot_dfs.items():
        snap_shot_dfs[key] = _amend_df(df, lifecycle["phase_code"], jira_filter)

    # return sshot_description, aging_dist, client_estimate_dist
    return snap_shot_dfs


def print_snapshot(sshot_description, aging_dist, client_estimate_dist):

    print("==== Total Client Estimate ====")
    # print(aging_dist["SumVal"].sum().style.format("${0:,.2f}"))
    print("${:,.0f}".format(aging_dist["SumVal"].sum()))

    # print results
    print("==== simple reiview of issues ====")
    print(sshot_description)

    print("\nHistogram of Aging")
    print(aging_dist)

    print("\nHistogram of client_estimate")
    print(client_estimate_dist)


# create running panda parquet files for
# . summary
# . aging
# . estimate bins
#
# for each job, script should support
# init (load historical data)
# load working data (filter to job, return pd)
# refresh data (open saved files, get new data from jira, ammend to saved file - 1/day most recent)

"""Defie list of estimating life cycle phases to analyze.  Each may have a list
of jira filters to serve as datasets in the life cycle to evalutate"""

approved_waiting = {
    "filename": "approved_waiting.json",
    "statuses": ["In Backlog", "Scheduled"],
    "first_status": "In Backlog",
    "phase_code": "approved_waiting",
    "jira_filters": [
        "backlog_approved_waiting",
        "backlog_approved_waiting_solutions_only",
        "backlog_approved_waiting_not_solutions_only",
    ],
}

pending_approval = {
    "filename": "pending_statuses.json",
    "statuses": ["Response Review", "Pending Client Input", "Sent to Client"],
    "first_status": "Sent to Client",
    "phase_code": "pending_approval",
    "jira_filters": ["backlog_sent_to_client"],
}

estimating = {
    "filename": "estimating.json",
    "statuses": ["Planning", "Needs Estimate", "Prep Client SOW"],
    "first_status": "Planning",
    "phase_code": "estimating",
    "jira_filters": ["backlog_estimating_all"],
}

in_flight = {
    "filename": "in_flight.json",
    "statuses": ["In Delivery", "Ready for Invoice", "Pending Close"],
    "first_status": "In Delivery",
    "phase_code": "in_flight",
    "jira_filters": ["backlog_in_flight", "backlog_in_flight_solutions_only"],
}

approved_in_flight = {
    "filename": "approved_in_flight.json",
    "statuses": [
        "In Backlog",
        "Scheduled",
        "In Delivery",
        "Ready for Invoice",
        "Pending Close",
    ],
    "first_status": "In Backlog",
    "phase_code": "approved_in_flight",
    "jira_filters": ["backlog_approved_in_flight"],
}

recently_completed = {
    "filename": "recently_completed.json",
    "statuses": [
        "Planning",  # estimating
        "Needs Estimate",
        "Prep Client SOW",
        "Response Review",  # pending approval
        "Pending Client Input",
        "Sent to Client",
        "In Backlog",  # approved
        "Scheduled",
        "In Delivery",  # in_flight
        "Ready for Invoice",
        "Pending Close",
        "Complete",  # Complete
    ],
    "first_status": "Planning",
    "phase_code": "recently_completed",
    "jira_filters": ["backlog_recently_completed"],
}


def main():

    """List of jobs of life cycles to iterate over"""
    # lifecycles = [approved_waiting, pending_approval]
    # lifecycles = [estimating, pending_approval, approved_waiting, in_flight]
    # lifecycles = [estimating]
    lifecycles = [recently_completed]

    for lc in lifecycles:
        for jfilter in lc["jira_filters"]:
            new_snapshot = get_snapshot(lc, jfilter)
            # todo: save to history here. (send to metabase?)
            print_snapshot(
                new_snapshot["sshot_description"],
                new_snapshot["aging_dist"],
                new_snapshot["client_estimate_dist"],
            )


if __name__ == "__main__":
    main()
