# %%
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import json
import pandas as pd
import collections

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


def get_issues_from_filter_page(filter, start_at=0):
    """return dictionary of issues in filter
    filter - filter name
    getall - if true, iterate through pagination"""
    max_results = 20

    url = "search"
    params = {
        "jql": "filter=" + filter,
        "fields": "key,summary,status,created,customfield_14925,customfield_12513",
        "maxResults": max_results,
        "startAt": start_at,
    }

    issues = _get(url, params)
    return issues


def get_issues_from_filter(filter, getall=False, start_at=0):
    """return dictionary of issues in filter
    filter - filter name
    getall - if true, iterate through pagination"""

    only_issues = []
    issues = get_issues_from_filter_page(filter)
    only_issues = only_issues + issues["issues"]

    # check to see if we got them all
    nextpage = issues["startAt"] + len(only_issues)
    while nextpage < issues["total"]:
        next_issues = get_issues_from_filter_page(filter, start_at=nextpage)
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
    """Return issue dictionary of issue change log"""

    issueid = issueid
    url = "issue/" + issueid + "/changelog"

    issue_log = _get(url)
    return issue_log


def get_status_changes_old(issue_log, status_list):
    """Decided to do this a different way.
    return dataframe of age of status
    issure_log - dictionary of jira change log
    status_list - list of statuses to extract"""
    status_changes = collections.defaultdict(list)
    for v in issue_log["values"]:
        for i in v["items"]:
            if i["field"] == "status" and i["toString"] in status_list:
                status_changes["id"].append(v["id"])
                status_changes["created"].append(v["created"])
                status_changes["fromString"].append(i["fromString"])
                status_changes["toString"].append(i["toString"])
    return status_changes
    # todo: this works, but should be later in the process
    sc = pd.DataFrame(status_changes)

    sc["created"] = pd.to_datetime(sc["created"], utc=True)
    sc["days_since"] = (sc["created"] - pd.Timestamp.now(tz="UTC")).dt.days
    return sc


"""
 # get issues from filter
 # get transistions form chage log
 #      todo: deal w/ multiple trans to same status
 # todo:calculate date delta
 # todo:put in pd.dataframe, calc date buckets for aging
 # todo:make visualization
"""


def get_transistions_for_issues(jira_issues, status_list):
    """return dictionary of issues w/ status change information"""
    status_list = status_list
    issues = []
    for i in jira_issues:
        issue = {}

        issue["key"] = i["key"]
        issue["summary"] = i["fields"]["summary"]
        issue["client_estimate"] = i["fields"]["customfield_14925"]
        issue["client"] = i["fields"]["customfield_12513"]["value"]
        issue["created"] = i["fields"]["created"]
        issue["current_status"] = i["fields"]["status"]["name"]
        # assemble the list of status transitions
        issue["transistions_sold"] = []
        issue["transistions_sold"].append(
            get_status_changes(get_issue_changelog(i["key"]), status_list)
        )

        issues.append(issue)
    # pprint(issue
    return issues


def get_status_changes(issue_log, status_list):
    """return an transistions dict from an issue's log"""
    status_changes = []
    for v in issue_log["values"]:
        for i in v["items"]:
            if i["field"] == "status" and i["toString"] in status_list:
                status_change = {}
                status_change["created"] = v["created"]
                status_change["fromString"] = i["fromString"]
                status_change["toString"] = i["toString"]
                status_changes.append(status_change)
    return status_changes


def export_json(dict, file):
    """ save a json dictionary to a file for later
    dict - json dictionary to save
    file - filename to save"""
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
        w_jira_issues = get_issues_from_filter("backlog_approved_waiting")
        w_issues = get_transistions_for_issues(w_jira_issues, sold_statuses["statuses"])
        # pprint(sold_issues)
        export_json(sold_issues, w_issues_file)

    if source == "local":
        try:
            w_issues = json.load(open(w_issues_file))
        except FileNotFoundError as nofile:
            print(f"File not fount: {nofile}")
            raise nofile

    return w_issues


# initally, we'll evaluate aging on "sold" status. but a similar evalutaion of
# pending status is likely worthwhile.
sold_statuses = {
    "filename": "sold_statuses.json",
    "statuses": ["In Backlog", "Scheduled"],
}

pending_statuses = {
    "filename": "pending _statuses.json",
    "statuses": ["Sent to Client", "Response Review"],
}

# %%
# use "local" or "jira" to indicate whether to actually hit the jira api.
pending_issues = get_working_issues(pending_statuses, "local")
print(len(pending_statuses))
sold_issues = get_working_issues(sold_statuses, "local")
print(len(sold_issues))

# %%
