"""Behavior tests for the access-log query script.

Purpose:
- Give the script an Athena client that behaves the way Athena does (queries
  run for a while, results come in pages with a header row first) and assert
  on the JSON it prints and on how it fails.
"""

import datetime
import json

import pytest

import query_logs
from stack.polls_access_log_queries import QUERIES

TODAY = datetime.date(2026, 10, 17)
WORKGROUP = "NateNiteProductionPolls-access-logs"
DATABASE = "nateniteproductionpolls_access_logs"


class FakeAthena:  # pylint: disable=too-few-public-methods
    """Athena stand-in: queries finish after `polls` checks, results page."""

    PAGE_SIZE = 2

    def __init__(self, rows=None, polls=0, final_state="SUCCEEDED"):
        self.rows = rows if rows is not None else [{"c_ip": "1", "n": "2"}]
        self.polls = polls
        self.final_state = final_state
        self.started = []
        self.stopped = []
        self._checks = {}

    def start_query_execution(self, **kwargs):
        """Record the query and hand back an id."""
        self.started.append(kwargs)
        return {"QueryExecutionId": f"q{len(self.started)}"}

    def get_query_execution(self, QueryExecutionId):  # noqa: N803
        """Report RUNNING for `polls` checks, then the final state."""
        # pylint: disable=invalid-name
        seen = self._checks.get(QueryExecutionId, 0)
        self._checks[QueryExecutionId] = seen + 1
        state = "RUNNING" if seen < self.polls else self.final_state
        status = {"State": state}
        if state == "FAILED":
            status["StateChangeReason"] = "SYNTAX_ERROR: no such column"
        return {"QueryExecution": {"Status": status}}

    def stop_query_execution(self, QueryExecutionId):  # noqa: N803
        """Record the cancellation."""
        # pylint: disable=invalid-name
        self.stopped.append(QueryExecutionId)

    def get_query_results(
        self, QueryExecutionId, NextToken=None
    ):  # noqa: N803
        """One page of results; only the first page starts with the header."""
        # pylint: disable=invalid-name,unused-argument
        columns = sorted(self.rows[0]) if self.rows else ["c_ip"]
        start = int(NextToken or 0)
        page = self.rows[start : start + self.PAGE_SIZE]
        data = [
            {"Data": [{"VarCharValue": str(row[c])} for c in columns]}
            for row in page
        ]
        if start == 0:
            data.insert(
                0, {"Data": [{"VarCharValue": column} for column in columns]}
            )
        result = {"ResultSet": {"Rows": data}}
        if start + self.PAGE_SIZE < len(self.rows):
            result["NextToken"] = str(start + self.PAGE_SIZE)
        return result


def run(athena, days=90, **kwargs):
    """Run the script's entry point against the fake, no real waiting."""
    return query_logs.query_logs(
        athena,
        workgroup=WORKGROUP,
        database=DATABASE,
        days=days,
        today=TODAY,
        sleep=lambda _seconds: None,
        **kwargs,
    )


@pytest.mark.unit
def test_it_reports_every_saved_query_over_the_window():
    """One entry per routine question, with the window it covered."""
    report = json.loads(run(FakeAthena(), days=90))
    assert report["days"] == 90
    assert (report["from"], report["to"]) == ("2026-07-19", "2026-10-17")
    assert sorted(report["queries"]) == sorted(QUERIES)
    assert report["queries"]["polls/top-client-addresses"] == [
        {"c_ip": "1", "n": "2"}
    ]


@pytest.mark.unit
def test_each_query_runs_in_the_workgroup_for_the_requested_days():
    """The SQL is the saved one, filled in for the window, nothing left over."""
    athena = FakeAthena()
    run(athena, days=45)
    assert len(athena.started) == len(QUERIES)
    for call in athena.started:
        assert call["WorkGroup"] == WORKGROUP
        assert call["QueryExecutionContext"] == {"Database": DATABASE}
        assert "interval '45' day" in call["QueryString"]
        assert "{" not in call["QueryString"]


@pytest.mark.unit
def test_output_is_the_same_text_for_the_same_data():
    """Sorted keys and fixed indentation, so diffs and automation are stable."""
    text = run(FakeAthena(rows=[{"b": "1", "a": "2"}]))
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True)


@pytest.mark.unit
def test_results_over_several_pages_are_all_returned_without_the_header():
    """The header row is on the first page only."""
    rows = [{"c_ip": str(number)} for number in range(5)]
    report = json.loads(run(FakeAthena(rows=rows)))
    assert report["queries"]["polls/errors-by-day"] == rows


@pytest.mark.unit
def test_a_query_with_no_rows_gives_an_empty_list():
    """No problems found is an answer, not an error."""
    report = json.loads(run(FakeAthena(rows=[])))
    assert report["queries"]["polls/blocked-and-throttled"] == []


@pytest.mark.unit
def test_it_waits_for_a_running_query():
    """Queries take a while; keep checking until they finish."""
    athena = FakeAthena(polls=3)
    report = json.loads(run(athena))
    assert sorted(report["queries"]) == sorted(QUERIES)


@pytest.mark.unit
def test_a_failed_query_stops_the_run_and_says_why():
    """No partial report: the reason is raised, later queries never start."""
    athena = FakeAthena(final_state="FAILED")
    with pytest.raises(query_logs.QueryFailed, match="no such column"):
        run(athena)
    assert len(athena.started) == 1


@pytest.mark.unit
def test_a_query_that_never_finishes_is_cancelled():
    """Give up after the time limit, and don't leave it running."""
    athena = FakeAthena(polls=10**6)
    with pytest.raises(query_logs.QueryFailed, match="did not finish"):
        run(athena, max_wait_seconds=10)
    assert athena.stopped == ["q1"]
