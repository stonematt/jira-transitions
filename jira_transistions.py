# This code sample uses the 'requests' library:
# http://docs.python-requests.org
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from pprint import pprint
import json
import time
import pandas as pd
import collections


token = json.load(open("me.json"))


# cloudID = "029ed131-584c-4a3e-b4ae-473022fcbdd6"
# urlbase = "https://api.atlassian.com/ex/jira/" + cloudID + "/rest/api/3/"
# # auth = HTTPBasicAuth("email@example.com", "<api_token>")
# auth = HTTPBasicAuth(token["user"], token["token"])
# headers = {"Accept": "application/json"}


def _get(url, params={}):
    cloudID = "029ed131-584c-4a3e-b4ae-473022fcbdd6"
    urlbase = "https://api.atlassian.com/ex/jira/" + cloudID + "/rest/api/3/"
    # auth = HTTPBasicAuth("email@example.com", "<api_token>")
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
        # print(r.text)
        return json.loads(r.text)


def list_filters():
    filters = _get("filter/my")
    return filters


def print_filters():
    for f in list_filters():
        print(f"{f['id']}, {f['name']} ")


def get_issue(issueid):
    """returns a json blob of issue details"""
    id = issueid
    url = "issue/" + id

    params = {"expand": "transitions"}
    issue = _get(url, params)
    return issue


def get_issue_transistions(issueid):
    id = issueid
    url = "issue/" + id + "/transitions"

    issue_transitions = _get(url)
    return issue_transitions


def get_issue_changelog(issueid):
    id = issueid
    url = "issue/" + id + "/changelog"

    issue_log = _get(url)
    return issue_log


def get_status_changes(log, status_list):
    """return dataframe of age of status
    log - dictionary of jira change log
    status_list - list of statuses to extract"""
    status_changes = collections.defaultdict(list)
    for v in log["values"]:
        for i in v["items"]:
            if i["field"] == "status" and i["toString"] in status_list:
                # elapsed =
                # print(f"{v['id']}, {v['created']}, {i['fromString']}, {i['toString']} ")
                status_changes["id"].append(v["id"])
                status_changes["created"].append(v["created"])
                status_changes["fromString"].append(i["fromString"])
                status_changes["toString"].append(i["toString"])
    sc = pd.DataFrame(status_changes)

    sc["created"] = pd.to_datetime(sc["created"], utc=True)
    sc["days_since"] = (sc["created"] - pd.Timestamp.now(tz="UTC")).dt.days
    # print(sc)
    return sc


### playground
log = get_issue_changelog("support-60933")


sold_statuses = ["In Backlog", "Scheduled"]
pending_statuses = ["Sent to Client", "Response Review"]
sold = get_status_changes(log, sold_statuses)

pending = get_status_changes(log, pending_statuses)

#### program
# get issues from filter
# for each issue get transistion

# from transistion, find date of status x->y change
