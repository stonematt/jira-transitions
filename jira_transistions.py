# %%
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import json
import pandas as pd
from datetime import datetime


# this includes an individuals api key.  use it carefully it.
token = json.load(open("me.json"))
datadir = "./data/"
examplesdir = "./examples/"


def _get(url, params={}):
    cloudID = "029ed131-584c-4a3e-b4ae-473022fcbdd6"
    urlbase = "https://api.atlassian.com/ex/jira/" + cloudID + "/rest/api/3/"
    auth = HTTPBasicAuth(token["user"], token["token"])
    headers = {"Accept": "application/json"}

    url = urlbase + url
    params = params

    try:
        r = requests.request("GET", url, headers=headers, auth=auth, params=params)
    except HTTPError as hterr:
        print(f"HTTPError: {hterr}")
        raise hterr
    else:
        return json.loads(r.text)


def list_filters():
    filters = _get("filter/my")
    return filters


def print_filters():
    for f in list_filters():
        print(f"{f['id']}, {f['name']} ")


def get_issues_from_filter_page(jira_filter, start_at=0):
    """return dictionary of issues in filter
    jira_filter - filter name
    getall - if true, iterate through pagination"""
    max_results = 20

    url = "search"
    params = {
        "jql": "filter=" + jira_filter,
        "fields": "key,summary,status,created,customfield_14925,customfield_12513",
        "maxResults": max_results,
        "startAt": start_at,
    }

    issues = _get(url, params)
    return issues


def get_issues_from_filter(jira_filter, getall=False, start_at=0):
    """return dictionary of issues in filter
    jira_filter - filter name
    getall - if true, iterate through pagination"""

    only_issues = []
    issues = get_issues_from_filter_page(jira_filter)
    only_issues = only_issues + issues["issues"]
    print(f"\nTotal issues to get: {issues['total']}")

    # check to see if we got them all
    nextpage = issues["startAt"] + len(only_issues)
    while nextpage < issues["total"]:
        next_issues = get_issues_from_filter_page(jira_filter, start_at=nextpage)
        only_issues = only_issues + next_issues["issues"]
        nextpage = next_issues["startAt"] + len(next_issues["issues"])

    # print(f"only issues: {len(only_issues)}")

    return only_issues


def get_issue(issueid):
    """returns a json blob of issue details"""
    issueid = issueid
    url = "issue/" + issueid

    params = {"expand": "transitions"}
    issue = _get(url, params)
    return issue


def get_issue_changelog(issueid):
    """Return issue dictionary of issue change log """

    issueid = issueid
    url = "issue/" + issueid + "/changelog"

    issue_log = _get(url)
    return issue_log


"""
 # get issues from filter
 # get transistions form chage log
 #      deal w/ multiple trans to same status
 # put in pd.dataframe,
 #      todo:calc date buckets for aging
 # todo:make visualization
"""


def _to_date(jira_date):
    """ return datetime object of date from jira time string
    that looks like: 2021-10-05T14:12:44.872-0400
    """
    d = datetime.strptime(jira_date, "%Y-%m-%dT%H:%M:%S.%f%z")
    return d


def get_transistions_for_issues(jira_issues, status_list):
    """return dictionary of issues w/ status change information"""
    status_list = status_list
    issues = []
    progress = 0
    for i in jira_issues:
        progress += 1
        if progress % 20 == 0:
            print(f"{progress} issues processed")

        issue = {}

        issue["key"] = i["key"]
        issue["summary"] = i["fields"]["summary"]
        issue["client_estimate"] = i["fields"]["customfield_14925"]
        # somtimes client isn't set and this would blow up
        issue["client"] = (
            i["fields"]["customfield_12513"]["value"]
            if i["fields"]["customfield_12513"]
            else None
        )
        # var1 = 4 if var1 is None else var1
        issue["created"] = i["fields"]["created"]
        issue["current_status"] = i["fields"]["status"]["name"]
        # todo: targetdate

        change_log = get_status_changes_summary(
            get_issue_changelog(i["key"]), status_list
        )
        issue.update(change_log)

        issues.append(issue)
    # pprint(issue
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

    # export_json(status_changes, "./deleteme.statuschanges.json")
    return status_changes


def _generate_aging_names(lifecycle_phase):
    aging_start = lifecycle_phase["first_status"] + "_last"
    aging_name = lifecycle_phase["phase_code"] + "_age"
    aging_bins = "aging_bins"

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
    # todo: calculate days remaining

    # set aging bins
    bins = [0, 7, 14, 30, 60, 90, 120, 10000]
    lables = ["07d", "14d", "30d", "60d", "90d", "120d", "very old"]
    sc[aging_bins] = pd.cut(sc[aging_name], bins=bins, labels=lables)

    # set estimate bins
    estbins = [0, 500, 1000, 2000, 5000, 10000, 20000, 1000000]
    estlables = ["<500", "<1000", "<2000", "<5000", "<10000", "<20000", "More"]
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
    """ save a json dictionary to a file for later

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

    w_issues_file = (
        examplesdir + status_list["phase_code"] + "_" + jira_filter + ".json"
    )

    if source == "jira":
        w_jira_issues = get_issues_from_filter(jira_filter)
        w_issues = get_transistions_for_issues(w_jira_issues, status_list["statuses"])
        export_json(w_issues, w_issues_file)

    if source == "local":
        try:
            w_issues = json.load(open(w_issues_file))
        except FileNotFoundError as nofile:
            print(f"File not found: {nofile}")
            raise nofile

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


def get_snapshot(lifecycle, jira_filter, source="jira"):
    """Get current data snapshot from jira for a lifecycle phase from a jira filter
    This is the content to send to metabase

    Args:
        lifecycle (dict): lifecycle phase in the jira sales pipeline
        jira_filter (string): name of a saved jira filter
        source (string): jira (default) or local

    Results: updates the history_dfs[key]["snap_shot"] key with the current snap_shot
        for each of description, aging_dist_history, and client_estimates_history
    """

    aging_start, aging_name, aging_bins = _generate_aging_names(lifecycle)

    print(f"Fetching data from {jira_filter}")
    # use "local" or "jira" to indicate whether to actually hit the jira api.

    snap_shot = get_working_issues(lifecycle, jira_filter, source)

    # make relevant dataframes
    sshot = issues_to_pandas(snap_shot, lifecycle)

    # snap_shot_dfs["sshot_description"] = sshot.describe(
    history_dfs["description"]["snap_shot"] = sshot.describe(
        percentiles=[0.25, 0.5, 0.8, 0.9]
    ).round(2)

    history_dfs["aging_dist_history"]["snap_shot"] = category_distribution(
        sshot, aging_bins
    )

    history_dfs["client_estimate_history"]["snap_shot"] = category_distribution(
        sshot, "client_estimate_bins"
    )

    # add columns for todays date, phase, and jira filter for reporting
    # snap_shot_dfs = [sshot_description, aging_dist, client_estimate_dist]
    for hist in history_dfs:
        hss = history_dfs[hist]["snap_shot"]
        hss = _amend_df(hss, lifecycle["phase_code"], jira_filter)


def print_snapshot(sshot_description, aging_dist, client_estimate_dist):

    # print results
    print("==== simple reiview of issues ====")
    print(sshot_description)

    print("\nHistogram of Aging")
    print(aging_dist)

    print("\nHistogram of client_estimate")
    print(client_estimate_dist)


def load_all_history(history_dfs):
    """loads history from csv and returns 3 dataframes"""

    # init history in memory as dataframes

    for history in history_dfs:
        csv_fn = datadir + history_dfs[history]["history_file"] + ".csv"
        try:
            history_dfs[history]["history_df"] = pd.read_csv(csv_fn)
        except FileNotFoundError as nofile:
            print(f"No history file found:\n {nofile}")
            # raise nofile
            history_dfs[history]["history_df"] = ""
        else:
            return

    return True


def _save_df_tocsv(hist_df_key):
    csv_fn = datadir + hist_df_key["history_file"] + ".csv"

    try:
        hist_df_key["history_df"].to_csv(csv_fn)
    except FileNotFoundError as nofile:
        print(f"No history file found:\n {nofile}")
        raise nofile

    return True


def save_history(history_dfs, df_key):
    # save history file to disk

    return True


def append_snapshot(hist_df_key):
    # histdf = hist_df_key["history_df"]
    hss = hist_df_key["snap_shot"]
    # print(f"snaphot len: {len(hss)} hist len: {len(histdf)}")
    if "history_df" in hist_df_key.keys():
        # histdf.append(hss, ignore_index=False)
        new_hist = pd.concat([hist_df_key["history_df"], hss], ignore_index=True)
    else:
        hist_df_key["history_df"] = hss
        new_hist = hist_df_key["history_df"]
    return new_hist


def update_histories(lifecycle, jira_filter):
    # get df_key from history, remove "today" for this lc/filter, add snapshot

    for hist in history_dfs:
        hk = history_dfs[hist]
        # history_dfs[hist]["history_df"] = append_snapshot(history_dfs[hist])
        hk["history_df"] = append_snapshot(history_dfs[hist])

        print(
            f"snaphot shape: {(hk['snap_shot'].shape)} hist .shape: {(hk['history_df'].shape)}"
        )
        # save to file
        _save_df_tocsv(hk)

    return True


"""history_dfs data library model:
    aggregation key:    the various ways we aggregage data about project to plot over time:
                        description, aging_dist_history, client_estimate_history
        history_file:    file location to store csv of history
        history_df:     dataframe of history data - it will be saved to csv for future use
        snap_shot:      dataframe of most recent "get_snapshot" - it will be appended to the
                        history data frame and then ignored or removed
"""
history_dfs = {
    "description": {"history_file": "description_history"},
    "aging_dist_history": {"history_file": "aging_dist_history"},
    "client_estimate_history": {"history_file": "client_estimate_history"},
}

"""Defie list of estimating life cycle phases to analyze.  Each may have a list
of jira filters to serve as datasets in the life cycle to evalutate"""

lifecycles = {
    "approved_waiting": {
        "filename": "approved_waiting",
        "statuses": ["In Backlog", "Scheduled"],
        "first_status": "In Backlog",
        "phase_code": "approved_waiting",
        "jira_filters": [
            "backlog_approved_waiting",
            "backlog_approved_waiting_solutions_only",
        ],
    },
    "pending_approval": {
        "filename": "pending_statuses",
        "statuses": ["Response Review", "Pending Client Input", "Sent to Client"],
        "first_status": "Sent to Client",
        "phase_code": "pending_approval",
        "jira_filters": ["backlog_sent_to_client"],
    },
    "estimating": {
        "filename": "estimating",
        "statuses": ["Planning", "Needs Estimate", "Prep Client SOW"],
        "first_status": "Planning",
        "phase_code": "estimating",
        "jira_filters": ["backlog_estimating_all"],
    },
    "in_flight": {
        "filename": "in_flight",
        "statuses": ["In Delivery", "Ready for Invoice", "Pending Close"],
        "first_status": "In Delivery",
        "phase_code": "in_flight",
        "jira_filters": ["backlog_in_flight", "backlog_in_flight_solutions_only"],
    },
}
otherlc = {
    "ttc": {
        "filename": "ttc",
        "statuses": [
            "In Backlog",
            "Scheduled",
            "In Delivery",
            "Ready for Invoice",
            "Pending Close",
            "Complete",
        ],
        "first_status": "In Delivery",
        "phase_code": "ttc",
        "jira_filters": ["SuccessProjectBacklogComplete"],
    },
}

# todo: load all history


def main():
    activelc = otherlc

    for lc in activelc:  # chance back to lifecycles for real
        for jfilter in activelc[lc]["jira_filters"]:
            get_snapshot(activelc[lc], jfilter, "local")
            # todo: save to history here. (send to metabase?)
            update_histories(activelc[lc], jfilter)
            print_snapshot(
                history_dfs["description"]["snap_shot"],
                history_dfs["aging_dist_history"]["snap_shot"],
                history_dfs["client_estimate_history"]["snap_shot"],
            )


if __name__ == "__main__":
    main()
