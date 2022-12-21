# %%
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
import json
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
    issue_count = r.get("total") if r.get("total") else 0
    # # print(f"total issues: {issue_count}")

    return issue_count


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


def date_range_from_end(end_date, dayspan=28):

    e = datetime.strftime(end_date, "%Y-%m-%d")
    start_date = datetime.strftime((end_date - timedelta(days=dayspan)), "%Y-%m-%d")

    return start_date, e


def generate_jql(j_status, start_date, end_date, from_status=[]):
    """needs a status and a date range with dates as string"""

    jql_base = "(project = 'Client Success' \
        AND 'Customer Request Type' in ('Technical Services Project (SUPPORT)', 'Engineering Project (SUPPORT)') \
        OR issuetype = SOW AND status not in (Suspended) AND 'General Services SOW' is EMPTY)  \
        AND status changed to '"

    during_jql = "' during ('" + start_date + "', '" + end_date + "')"

    # "type in (sow, 'Technical Services Project') AND status changed to '"
    jql = jql_base + j_status + during_jql

    # todo: not sure this is the best way to do this
    if len(from_status) > 0:
        from_jql = " AND (status changed from '" + from_status[0] + during_jql
        if len(from_status) > 1:
            for s in from_status[1:]:
                from_jql = from_jql + " OR status changed from '" + s + during_jql
        from_jql = from_jql + ")"
        jql = jql + from_jql

    # print(jql)

    return jql


def get_datapoint(status, jstart, jend, from_status=[]):
    """return count of issues"""

    status_count = count_issues_from_jql(
        generate_jql(status, jstart, jend, from_status)
    )
    return status_count


def get_data_for_day(j_balance, end_date, days=28):
    """expect python date/time"""

    datapoint = {"date": datetime.strftime(end_date, "%Y-%m-%d"), "days": days}

    if "in_from" in j_balance.keys():
        from_list = j_balance["in_from"]
    else:
        from_list = []

    jstart, jend = date_range_from_end(end_date, days)

    datapoint["in_count"] = get_datapoint(
        j_balance["in_status"], jstart, jend, from_list
    )
    datapoint["out_count"] = get_datapoint(j_balance["out_status"], jstart, jend)
    datapoint["raw_delta"] = datapoint["out_count"] - datapoint["in_count"]

    def in_wks(value, days):
        p_wk = value / days * 7
        return p_wk

    datapoint["in_p_wk"] = in_wks(datapoint["in_count"], days)
    datapoint["out_p_wk"] = in_wks(datapoint["out_count"], days)
    datapoint["delta_p_wk"] = in_wks(datapoint["raw_delta"], days)

    return datapoint


def load_history_from_file(filename):

    try:
        report = json.load(open(filename))
    except FileNotFoundError as nofile:
        print(f"File not found: {nofile}")
        # raise nofile
        report = []

    return report


def get_data_for_daterange(j_balance, end_date, start_date, history_report=[]):
    """j_balance - balance to calculate
    end_date: python datetime
    start_date: python dateteime
    history_report: dictionary of balances"""

    report = history_report

    for i in range((end_date - start_date).days):
        rdate = start_date + i * timedelta(days=1)
        datapoint = datetime.strftime(rdate, "%Y-%m-%d")
        print(datapoint)
        report.append(get_data_for_day(j_balance, rdate))

        # probably don't need to do this on every data point...
        export_json(report, datadir + j_balance["hist_file"])

    return report


def update_recent_days(
    j_balance, report, end_date=datetime.today().date(), report_span=10, start_date=""
):
    """take a report as dictionary, find most recent date, update to now
    this assumes the report stops at 'yesterday'"""

    yesterday = datetime.today().date() - timedelta(days=1)
    yesterday_s = datetime.strftime(yesterday, "%Y-%m-%d")

    # if the passed in report has history, update form last date to now
    if len(report) > 0:
        # get the most recent date in the report and delete it if it's yesterday
        last_date = datetime.strptime(
            max(report, key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))["date"],
            "%Y-%m-%d",
        ).date()
        if last_date == yesterday:
            del report[
                report.index(
                    next(filter(lambda d: d.get("date") == yesterday_s, report))
                )
            ]
            start_date = last_date
        else:
            start_date = last_date + timedelta(days=1)

    # if the passed in report is empty, generate history according to params
    else:
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_date = end_date - timedelta(days=report_span)

    report = get_data_for_daterange(j_balance, end_date, start_date, report)

    return report


jira_balances = {
    "approved": {
        "in_status": "In Backlog",
        "in_from": ["Response Review", "Needs Estimate"],
        "out_status": "Pending Communication",
        "hist_file": "approved_history.json",
    },
    "tsps": {
        "in_status": "In Backlog",
        "in_from": ["Response Review", "Needs Estimate"],
        "out_status": "Complete",
        "hist_file": "tsp_history.json",
    },
    "estimates": {
        "in_status": "Planning",
        "out_status": "Prep Client SOW",
        "hist_file": "estimates_history.json",
    },
}


def main():

    # jira_balances = q_balances

    for jb in jira_balances:
        jira_balance = jira_balances[jb]
        history = update_recent_days(
            jira_balance,
            load_history_from_file(datadir + jira_balance["hist_file"]),
            report_span=40,
        )

        print(f"Recent data from {jira_balance['hist_file']}")
        print(json.dumps(history[-1], sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
