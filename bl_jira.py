# %%
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import json
import streamlit as st
from datetime import datetime

token = {}
token["user"] = st.secrets["user"]
token["token"] = st.secrets["token"]


def _get(url, params={}):
    cloudID = "029ed131-584c-4a3e-b4ae-473022fcbdd6"
    urlbase = "https://api.atlassian.com/ex/jira/" + cloudID + "/rest/api/3/"
    auth = HTTPBasicAuth(token["user"], token["token"])
    headers = {"Accept": "application/json"}

    url = urlbase + url
    params = params

    r = requests.request("GET", url, headers=headers, auth=auth, params=params)

    try:
        r.raise_for_status()
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


# %%
def get_issues_from_jql_page(jql, start_at=0):
    max_results = 20

    url = "search"
    params = {
        "jql": jql,
        "fields": "key,summary,status,created,customfield_14925,customfield_12513,customfield_14922",
        "maxResults": max_results,
        "startAt": start_at,
    }

    issues = _get(url, params)
    return issues


def get_issues_from_filter_page(jira_filter, start_at=0):
    """return dictionary of issues in filter
    jira_filter - filter name
    getall - if true, iterate through pagination"""
    max_results = 20

    url = "search"
    params = {
        "jql": "filter=" + jira_filter,
        "fields": "key,summary,status,created,customfield_14925,customfield_12513,customfield_14922",
        "maxResults": max_results,
        "startAt": start_at,
    }

    issues = _get(url, params)
    return issues


def count_issues_in_filter(jira_filter):
    issues = get_issues_from_filter_page(jira_filter)
    total = issues["total"]
    return total


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

    # print(f"{len(only_issues)} issues processed")

    return only_issues


def get_issue(issueid):
    """returns a json blob of issue details"""
    issueid = issueid
    url = "issue/" + issueid

    params = {"expand": "transitions"}
    issue = _get(url, params)
    return issue


def get_issue_changelog(issueid):
    """Return issue dictionary of issue change log"""

    issueid = issueid
    url = "issue/" + issueid + "/changelog"

    issue_log = _get(url)
    return issue_log


def _to_date(jira_date):
    """return datetime object of date from jira time string
    that looks like: 2021-10-05T14:12:44.872-0400
    """
    d = datetime.strptime(jira_date, "%Y-%m-%dT%H:%M:%S.%f%z")
    return d


# %%
def main():
    True


if __name__ == "__main__":
    main()


# %%
