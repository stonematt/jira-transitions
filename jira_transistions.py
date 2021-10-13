# %%
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import json
import pandas as pd
from datetime import datetime

# from pprint import pprint


# this includes an individuals api key.  use it carefully it.
token = json.load(open("me.json"))


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
    print(f"Total issues to get: {issues['total']}")

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


def get_issue_transistions(issueid):
    issueid = issueid
    url = "issue/" + issueid + "/transitions"

    issue_transitions = _get(url)
    return issue_transitions


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
        issue["client"] = i["fields"]["customfield_12513"]["value"]
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
        status_changes[status + "_count"] = 0

    for v in issue_log["values"]:
        for i in v["items"]:
            if i["field"] == "status" and i["toString"] in status_list:
                status_changes[i["toString"] + "_count"] += 1
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


def issues_to_pandas(status_changes):
    """
    return dataframe of age of status
    issue_log - dictionary of jira change log
    status_list - list of statuses to extract"""
    sc = pd.DataFrame(status_changes)
    sc["In Backlog_last"] = pd.to_datetime(sc["In Backlog_last"], utc=True)
    # todo: make other dates be dates

    sc["approved_age"] = (pd.Timestamp.now(tz="UTC") - sc["In Backlog_last"]).dt.days
    # todo: calculate days remaining

    # set aging bins
    bins = [0, 7, 14, 30, 60, 90, 120, 1000]
    lables = ["07d", "14d", "30d", "60d", "90d", "q120+", "very old"]
    sc["approval_age_labeled"] = pd.cut(sc["approved_age"], bins=bins, labels=lables)

    # set estimate bins
    estbins = [0, 500, 1000, 2000, 5000, 10000, 20000, 1000000]
    estlables = ["<500", "<1000", "<2000", "<5000", "<10000", "<20000", "More"]
    sc["client_estimate_bins"] = pd.cut(
        sc["client_estimate"], bins=estbins, labels=estlables
    )

    # todo: age bins on days remaining from target date.
    return sc


def category_distribution(status_changes, column):
    """show histogram and order value of approved work
    status_changes - dataframe from issues_to_pandas()
    column - the column to show distribution by"""

    print(f"Totaling: {status_changes['client_estimate'].sum()}")

    return (
        status_changes.groupby(column)["client_estimate"]
        .agg(Count="count", SumVal="sum", AvgVal="mean")
        .round(0)
    )


def export_json(dict, file):
    """ save a json dictionary to a file for later

    dict - json dictionary to save

    file - filename to save
    """
    with open(file, "w") as fp:
        json.dump(dict, fp, sort_keys=True, indent=2)


def get_working_issues(status_list, source="jira"):
    """use local or jira as issue source

    Arguments:
        status_list -- list of jira statuses to collect transistion data for

        source -- "jira" to go to jira or "local" to open local file

    Returns:
        dict of issues w/ status transition information
    """

    w_issues_file = "./examples/" + status_list["filename"]
    if source == "jira":
        w_jira_issues = get_issues_from_filter(jira_filter)
        w_issues = get_transistions_for_issues(w_jira_issues, sold_statuses["statuses"])
        # pprint(sold_issues)
        export_json(w_issues, w_issues_file)

    if source == "local":
        try:
            w_issues = json.load(open(w_issues_file))
        except FileNotFoundError as nofile:
            print(f"File not found: {nofile}")
            raise nofile

    return w_issues


# initally, we'll evaluate aging on "sold" status. but a similar evalutaion of
# pending status is likely worthwhile.
sold_statuses = {
    "filename": "sold_statuses.json",
    "statuses": ["In Backlog", "Scheduled"],
    "first_status": "In Backlog",
    "phase_code": "approved_waiting",
}

pending_statuses = {
    "filename": "pending_statuses.json",
    "statuses": ["Sent to Client", "Response Review"],
    "first_status": "Sent to Client",
    "phase_code": "pending_approval",
}

# %%
jira_filter = "backlog_approved_waiting"

print(f"Fetching data from {jira_filter}")
# use "local" or "jira" to indicate whether to actually hit the jira api.
sold_issues = get_working_issues(sold_statuses, "jira")

sc = issues_to_pandas(sold_issues)
print("==== simple reiview of issues ====")
print(sc.describe().round(2))

print("\nHistogram of days since approval")
print(category_distribution(sc, "approval_age_labeled"))

print("\nHistogram of client_estimate")
print(category_distribution(sc, "client_estimate_bins"))
# %%
