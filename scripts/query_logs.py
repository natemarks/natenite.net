#!/usr/bin/env python3
"""Run the routine access-log queries over a window and print JSON.

Purpose:
- Let the poll owner, or automation, discover recent problems with the
  polling application: errors by day, the busiest client addresses, and the
  requests that were blocked or throttled.

Usage:
- PYTHONPATH=. python3 scripts/query_logs.py [--days 90] [--app-env production]
- `make query-logs [days=90]`

Notes:
- The output is one JSON object (sorted keys) on stdout; nothing else is
  printed there. A query that fails or does not finish is reported on stderr
  with a non-zero exit, and no partial report is printed.
- Client addresses appear in the results: this is the owner's own log data.
"""

import argparse
import datetime
import json
import sys
import time

import boto3

from config.settings import get_actual_path
from stack.polls import PollsInput
from stack.polls_access_log_queries import (
    QUERIES,
    database_name,
    render_query,
    workgroup_name,
)

DEFAULT_DAYS = 90


class QueryFailed(Exception):
    """A query failed, was cancelled, or did not finish in time."""


def _wait_for(athena, query_id, sleep, max_wait_seconds):
    """Block until the query succeeds; raise with the reason if it doesn't."""
    waited = 0
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)[
            "QueryExecution"
        ]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            return
        if state in ("FAILED", "CANCELLED"):
            reason = status.get("StateChangeReason", "no reason given")
            raise QueryFailed(f"query {state.lower()}: {reason}")
        if waited >= max_wait_seconds:
            athena.stop_query_execution(QueryExecutionId=query_id)
            raise QueryFailed(
                f"query did not finish within {max_wait_seconds} seconds"
                " and was cancelled"
            )
        sleep(2)
        waited += 2


def _fetch_rows(athena, query_id):
    """Return the result rows as dicts, following pages; header dropped."""
    rows = []
    header = None
    token = None
    while True:
        kwargs = {"QueryExecutionId": query_id}
        if token:
            kwargs["NextToken"] = token
        page = athena.get_query_results(**kwargs)
        for row in page["ResultSet"]["Rows"]:
            values = [cell.get("VarCharValue") for cell in row["Data"]]
            if header is None:
                header = values
            else:
                rows.append(dict(zip(header, values)))
        token = page.get("NextToken")
        if not token:
            return rows


def query_logs(  # pylint: disable=too-many-arguments
    athena,
    *,
    workgroup,
    database,
    days,
    today,
    sleep=time.sleep,
    max_wait_seconds=120,
):
    """Run every saved query for the last `days` days; return JSON text."""
    results = {}
    for name in QUERIES:
        started = athena.start_query_execution(
            QueryString=render_query(name, database, days),
            QueryExecutionContext={"Database": database},
            WorkGroup=workgroup,
        )
        query_id = started["QueryExecutionId"]
        _wait_for(athena, query_id, sleep, max_wait_seconds)
        results[name] = _fetch_rows(athena, query_id)
    report = {
        "days": days,
        "from": (today - datetime.timedelta(days=days)).isoformat(),
        "to": today.isoformat(),
        "queries": results,
    }
    return json.dumps(report, indent=2, sort_keys=True)


def open_athena(app_env, client=boto3.client):
    """Athena in the environment's configured region, with its names."""
    polls_input = PollsInput.from_config_directory(get_actual_path(app_env))
    region = polls_input.env_setting.default_region
    prefix = polls_input.prefix()
    return (
        client("athena", region_name=region),
        workgroup_name(prefix),
        database_name(prefix),
    )


def main():
    """Print the report for the window named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--app-env", default="production")
    args = parser.parse_args()

    athena, workgroup, database = open_athena(args.app_env)
    try:
        print(
            query_logs(
                athena,
                workgroup=workgroup,
                database=database,
                days=args.days,
                today=datetime.datetime.now(datetime.timezone.utc).date(),
            )
        )
    except QueryFailed as error:
        print(f"query-logs: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
