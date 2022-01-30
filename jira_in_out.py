# %%
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import json
import pandas as pd
from datetime import datetime, timedelta


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


def count_issues_from_jql(jql):
    """take jql return number of issues"""
    max_results = 20

    url = "search"
    params = {
        "jql": jql,
        "maxResults": max_results,
    }

    r = _get(url, params)
    try:
        issue_count = r["total"]
    except:
        issue_count = 0
    # print(f"total issues: {issue_count}")

    return issue_count


"""
 # get issues from filter
 # put in pd.dataframe,
 # todo:make visualization
"""


def _to_date(jira_date):
    """ return datetime object of date from jira time string
    that looks like: 2021-10-05T14:12:44.872-0400
    """
    d = datetime.strptime(jira_date, "%Y-%m-%dT%H:%M:%S.%f%z")
    return d


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

    aging_start = ""
    aging_name = ""

    sc = pd.DataFrame(status_changes)
    sc[aging_start] = pd.to_datetime(sc[aging_start], utc=True)
    sc["created"] = pd.to_datetime(sc["created"], utc=True)

    sc[aging_name] = (
        (pd.Timestamp.now(tz="UTC") - sc[aging_start]).where(
            pd.notna(sc[aging_start]), pd.Timestamp.now(tz="UTC") - sc["created"]
        )
    ).dt.days
    # todo: calculate days remaining

    return sc


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


def _save_df_tocsv(hist_df_key):
    csv_fn = datadir + hist_df_key["history_file"] + ".csv"

    try:
        hist_df_key["history_df"].to_csv(csv_fn)
    except FileNotFoundError as nofile:
        print(f"No history file found:\n {nofile}")
        raise nofile

    return True


# def _calc_period(date, days=28):
#     """take a date, return start/end date based on days
#     28 day default is 2 sprints"""
#     end_date = date


def date_range_from_end(end_date, dayspan=28):

    e = datetime.strftime(end_date, "%Y-%m-%d")
    start_date = datetime.strftime((end_date - timedelta(days=dayspan)), "%Y-%m-%d")

    return start_date, e


def generate_jql(j_status, start_date, end_date):
    """needs a status and a date range with dates as string"""

    jql = (
        "type in (sow, 'Technical Services Project') AND status changed to '"
        + j_status
        + "' during ('"
        + start_date
        + "', '"
        + end_date
        + "')"
    )
    # print(jql)

    return jql


def get_datapoint(status, jstart, jend):
    """return count of issues"""

    status_count = count_issues_from_jql(generate_jql(status, jstart, jend))
    return status_count


def get_data_for_day(j_balance, end_date, days=28):
    """expect python date/time"""

    datapoint = {"date": datetime.strftime(end_date, "%Y-%m-%d"), "days": days}

    jstart, jend = date_range_from_end(end_date, days)
    datapoint["in_count"] = get_datapoint(j_balance["in_status"], jstart, jend)
    datapoint["out_count"] = get_datapoint(j_balance["out_status"], jstart, jend)

    datapoint["raw_delta"] = datapoint["out_count"] - datapoint["in_count"]

    def in_wks(value, days):
        p_wk = value / days * 7
        return p_wk

    datapoint["in_p_wk"] = in_wks(datapoint["in_count"], days)
    datapoint["out_p_wk"] = in_wks(datapoint["out_count"], days)
    datapoint["delta_p_wk"] = in_wks(datapoint["raw_delta"], days)

    return datapoint


def get_data_for_daterange(j_balance, end_date, report_span=10):
    report_time_span = report_span
    report_end_date = end_date
    report_start_date = end_date - timedelta(days=report_time_span)

    report = []

    for i in range((report_end_date - report_start_date).days):
        rdate = report_start_date + i * timedelta(days=1)
        datapoint = datetime.strftime(rdate, "%Y-%m-%d")
        print(datapoint)
        report.append(get_data_for_day(j_balance, rdate))

        export_json(report, datadir + "/report.json")

    return report


jira_balances = {
    "solutions": {"in_status": "In Backlog", "out_status": "Pending Communication"},
    "another": {"in_status": "Planning", "out_status": "Prep Client SOW"},
}


def main():

    report_end_date = datetime.today()
    report = get_data_for_daterange(jira_balances["solutions"], report_end_date, 5)

    print(report)


if __name__ == "__main__":
    main()
