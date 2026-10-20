"""Behavior tests for the stored jq programs behind `make check-polls`.

Purpose:
- Run the real jq programs over fixture input and assert what they print, so
  a typo in one surfaces in the normal test run and not the first time the
  owner needs the check.
- No AWS credentials are needed: the fixtures stand in for what
  `aws logs filter-log-events` and `aws cloudwatch get-metric-data` return and
  for the lines the function logs.
"""

import json
import shutil
import subprocess

import pytest

from config.helper import PROJECT_ROOT

JQ_DIR = PROJECT_ROOT / "scripts" / "jq"

# 2026-10-16 12:00:00Z, 12:00:05Z and 12:01:00Z in milliseconds, worked out
# with `date -u -d`, not with the code under test.
T0, T5, T60 = 1792152000000, 1792152005000, 1792152060000


def jq(program, text, *flags):
    """Run a stored jq program over `text` and return its stdout."""
    if shutil.which("jq") is None:
        pytest.fail("jq is not installed; `make check-polls` needs it")
    result = subprocess.run(
        ["jq", *flags, "-f", str(JQ_DIR / program)],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def event(timestamp, message):
    """One entry of a `filter-log-events` response."""
    return {"timestamp": timestamp, "message": message}


def accepted(**extra):
    """A log line for an accepted submission, as the function writes it."""
    return {
        "level": "INFO",
        "outcome": "accepted",
        "status": 201,
        "pollId": "poll1",
        "responseId": "20261016T120000000000Z-0123456789abcdef",
        "bodyBytes": 40,
        "requestId": "req-1",
        **extra,
    }


def rejected(reason, status=400, **extra):
    """A log line for a rejected submission."""
    return {
        "level": "WARN",
        "outcome": "rejected",
        "status": status,
        "pollId": "poll1",
        "responseId": None,
        "bodyBytes": 40,
        "requestId": "req-2",
        "reason": reason,
        **extra,
    }


def failed(**extra):
    """A log line for a failure on our side."""
    return {
        "level": "ERROR",
        "outcome": "error",
        "status": 500,
        "pollId": "poll1",
        "responseId": None,
        "bodyBytes": 40,
        "requestId": "req-3",
        "reason": "internal_error",
        "errorType": "ClientError",
        "errorCode": "ProvisionedThroughputExceededException",
        **extra,
    }


def lines_from(response_text):
    """The JSON objects `polls_log_lines.jq` printed, one per line."""
    return [json.loads(line) for line in response_text.splitlines()]


@pytest.mark.unit
def test_log_lines_keep_the_functions_json_and_skip_platform_lines():
    """START, END and REPORT lines go; each kept line gains its timestamp."""
    response = {
        "events": [
            event(T0, "START RequestId: req-1 Version: $LATEST\n"),
            # The function prints its line with a trailing newline.
            event(T0, json.dumps(accepted()) + "\n"),
            event(T5, json.dumps(rejected("unknown_option")) + "\n"),
            event(T5, "END RequestId: req-1\n"),
            event(T5, "REPORT RequestId: req-1 Duration: 3.1 ms\n"),
            event(T60, json.dumps(failed()) + "\n"),
            # Valid JSON that is not one of the function's objects
            event(T60, "12345\n"),
        ],
        "searchedLogStreams": [],
    }

    out = jq("polls_log_lines.jq", json.dumps(response), "-c")

    assert lines_from(out) == [
        accepted(timestamp="2026-10-16T12:00:00Z"),
        rejected("unknown_option", timestamp="2026-10-16T12:00:05Z"),
        failed(timestamp="2026-10-16T12:01:00Z"),
    ]


@pytest.mark.unit
def test_log_lines_read_every_page_of_a_long_response():
    """Several pages' worth of output, one after another, are all read."""
    page_one = {"events": [event(T0, json.dumps(accepted()))]}
    page_two = {
        "events": [event(T5, json.dumps(rejected("poll_closed", 410)))]
    }

    out = jq(
        "polls_log_lines.jq",
        json.dumps(page_one) + "\n" + json.dumps(page_two),
        "-c",
    )

    assert [line["outcome"] for line in lines_from(out)] == [
        "accepted",
        "rejected",
    ]


@pytest.mark.unit
def test_log_lines_of_an_empty_window_are_empty():
    """No events, or no response body at all, prints nothing."""
    assert jq("polls_log_lines.jq", '{"events": []}', "-c") == ""
    assert jq("polls_log_lines.jq", "{}", "-c") == ""


def summary_of(lines):
    """The summary jq prints for the given log lines."""
    text = "\n".join(json.dumps(line) for line in lines)
    return json.loads(jq("polls_log_summary.jq", text, "-s"))


@pytest.mark.unit
def test_the_summary_counts_outcomes_rejections_and_lists_errors():
    """Rejections by reason, most frequent first; errors newest first."""
    older_error = failed(timestamp="2026-10-16T12:00:05Z", requestId="old")
    newer_error = failed(
        timestamp="2026-10-16T12:01:00Z",
        requestId="new",
        reason="email_not_stored",
        responseId="20261016T120100000000Z-aaaaaaaaaaaaaaaa",
    )
    lines = [
        accepted(timestamp="2026-10-16T12:00:00Z"),
        rejected("unknown_option", timestamp="2026-10-16T12:00:01Z"),
        older_error,
        accepted(timestamp="2026-10-16T12:00:06Z"),
        rejected("unknown_option", timestamp="2026-10-16T12:00:07Z"),
        rejected("poll_closed", 410, timestamp="2026-10-16T12:00:08Z"),
        rejected("invalid_email", timestamp="2026-10-16T12:00:09Z"),
        accepted(timestamp="2026-10-16T12:00:10Z"),
        newer_error,
    ]

    summary = summary_of(lines)

    assert summary == {
        "requests": 9,
        "outcomes": {"accepted": 3, "rejected": 4, "error": 2},
        "rejections_by_reason": [
            {"reason": "unknown_option", "count": 2},
            # Ties are broken by reason, alphabetically.
            {"reason": "invalid_email", "count": 1},
            {"reason": "poll_closed", "count": 1},
        ],
        "errors": [newer_error, older_error],
    }


@pytest.mark.unit
def test_the_summary_of_a_quiet_window_is_empty_but_well_formed():
    """No lines at all still gives the same four keys."""
    assert summary_of([]) == {
        "requests": 0,
        "outcomes": {},
        "rejections_by_reason": [],
        "errors": [],
    }


def metric_queries(**overrides):
    """The queries `polls_metric_queries.jq` builds for known arguments."""
    arguments = {
        "function": "polls-fn",
        "distribution": "DIST123",
        "account": "123456789012",
        "webacl": "SiteWebACL",
        **overrides,
    }
    flags = []
    for name, value in arguments.items():
        flags += ["--arg", name, value]
    text = jq("polls_metric_queries.jq", "null", "-n", *flags)
    return {query["Id"]: query for query in json.loads(text)}


@pytest.mark.unit
def test_the_metric_queries_cover_the_function_the_site_and_the_firewall():
    """Each series, with the names and dimensions confirmed in production."""
    lambda_dims = [{"Name": "FunctionName", "Value": "polls-fn"}]
    cloudfront_dims = [
        {"Name": "DistributionId", "Value": "DIST123"},
        {"Name": "Region", "Value": "Global"},
    ]
    expected = {
        "waf_polls": (
            "AWS/WAFV2",
            "BlockedRequests",
            "Sum",
            [
                {
                    "Name": "Resource",
                    "Value": "arn:aws:cloudfront::123456789012:distribution/"
                    "DIST123",
                },
                {"Name": "ResourceType", "Value": "CF"},
            ],
        ),
        "lambda_invocations": (
            "AWS/Lambda",
            "Invocations",
            "Sum",
            lambda_dims,
        ),
        "lambda_errors": ("AWS/Lambda", "Errors", "Sum", lambda_dims),
        "lambda_throttles": ("AWS/Lambda", "Throttles", "Sum", lambda_dims),
        "cloudfront_requests": (
            "AWS/CloudFront",
            "Requests",
            "Sum",
            cloudfront_dims,
        ),
        "cloudfront_4xx": (
            "AWS/CloudFront",
            "4xxErrorRate",
            "Average",
            cloudfront_dims,
        ),
        "cloudfront_5xx": (
            "AWS/CloudFront",
            "5xxErrorRate",
            "Average",
            cloudfront_dims,
        ),
    }

    queries = metric_queries()

    assert set(queries) == {*expected, "waf_rules"}
    for query_id, (namespace, name, stat, dimensions) in expected.items():
        metric = queries[query_id]["MetricStat"]
        assert metric["Metric"] == {
            "Namespace": namespace,
            "MetricName": name,
            "Dimensions": dimensions,
        }, query_id
        assert metric["Stat"] == stat, query_id


@pytest.mark.unit
def test_the_firewall_rule_query_searches_the_shared_acl_by_its_name_prefix():
    """The ACL's real name has a generated suffix, so it is a search term."""
    rules = metric_queries(webacl="MyAclPrefix")["waf_rules"]

    assert rules["Expression"] == (
        'SEARCH(\'{AWS/WAFV2,Rule,WebACL} MetricName="BlockedRequests" '
        "MyAclPrefix', 'Sum', 86400)"
    )
    assert "${PROP('Dim.Rule')}" in rules["Label"]


@pytest.mark.unit
def test_every_metric_query_is_daily_and_labelled_as_a_count_or_a_rate():
    """One-day periods (finer data expires), and a label the summary reads."""
    for query_id, query in metric_queries().items():
        if "MetricStat" in query:
            assert query["MetricStat"]["Period"] == 86400, query_id
        else:
            assert query["Expression"].endswith(", 86400)"), query_id
        assert query["Label"].startswith(("count: ", "rate: ")), query_id


def series(label, points, status="Complete", query_id="q"):
    """One entry of a `get-metric-data` response (newest day first)."""
    return {
        "Id": query_id,
        "Label": label,
        "Timestamps": [stamp for stamp, _ in points],
        "Values": [value for _, value in points],
        "StatusCode": status,
    }


def metrics_summary(*pages):
    """The summary jq prints for the given pages of results."""
    text = "\n".join(json.dumps({"MetricDataResults": page}) for page in pages)
    return json.loads(jq("polls_metrics_summary.jq", text, "-s"))


@pytest.mark.unit
def test_the_metrics_summary_reports_each_series_by_utc_day():
    """Counts get a total; rates do not; the peak day is named."""
    summary = metrics_summary(
        [
            series(
                "count: function errors",
                [
                    ("2026-10-17T00:00:00+00:00", 5.0),
                    ("2026-10-16T00:00:00+00:00", 2.0),
                    ("2026-10-15T00:00:00+00:00", 0.0),
                ],
            ),
            series(
                "rate: distribution 5xx error percent",
                [
                    ("2026-10-17T00:00:00+00:00", 0.5),
                    ("2026-10-16T00:00:00+00:00", 1.5),
                ],
            ),
        ]
    )

    assert summary == {
        "metrics": [
            {
                "kind": "count",
                "name": "function errors",
                "days": [
                    {"day": "2026-10-15", "value": 0.0},
                    {"day": "2026-10-16", "value": 2.0},
                    {"day": "2026-10-17", "value": 5.0},
                ],
                "max": 5.0,
                "max_day": "2026-10-17",
                "total": 7.0,
            },
            {
                "kind": "rate",
                "name": "distribution 5xx error percent",
                "days": [
                    {"day": "2026-10-16", "value": 1.5},
                    {"day": "2026-10-17", "value": 0.5},
                ],
                "max": 1.5,
                "max_day": "2026-10-16",
            },
        ],
        "incomplete": [],
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "stamp, day",
    [
        # The CLI writes the day that starts at 2026-10-17T00:00Z like this
        ("2026-10-16T20:00:00-04:00", "2026-10-17"),
        ("2026-10-17T00:00:00+00:00", "2026-10-17"),
        ("2026-10-17T00:00:00Z", "2026-10-17"),
        ("2026-10-17T05:30:00+05:30", "2026-10-17"),
        # A positive offset can put the UTC day before the written one
        ("2026-10-17T03:00:00+05:30", "2026-10-16"),
    ],
)
def test_a_timestamp_in_any_timezone_lands_on_its_utc_day(stamp, day):
    """The day is the UTC day, whatever timezone the CLI wrote it in."""
    summary = metrics_summary(
        [series("count: function errors", [(stamp, 1.0)])]
    )

    assert [entry["day"] for entry in summary["metrics"][0]["days"]] == [day]


@pytest.mark.unit
def test_series_sharing_an_id_stay_apart_and_pages_of_one_series_merge():
    """Search results share an id; a long series can span pages."""
    summary = metrics_summary(
        [
            series(
                "count: shared firewall blocked requests, rule A",
                [("2026-10-17T00:00:00+00:00", 3.0)],
                query_id="waf_rules",
            ),
            series(
                "count: shared firewall blocked requests, rule B",
                [("2026-10-17T00:00:00+00:00", 9.0)],
                query_id="waf_rules",
            ),
        ],
        [
            series(
                "count: shared firewall blocked requests, rule A",
                [("2026-10-16T00:00:00+00:00", 4.0)],
                query_id="waf_rules",
            )
        ],
    )

    by_name = {entry["name"]: entry for entry in summary["metrics"]}
    rule_a = by_name["shared firewall blocked requests, rule A"]
    assert [d["day"] for d in rule_a["days"]] == ["2026-10-16", "2026-10-17"]
    assert rule_a["total"] == 7.0
    assert by_name["shared firewall blocked requests, rule B"]["total"] == 9.0


@pytest.mark.unit
def test_series_that_did_not_come_back_complete_are_named():
    """A partial or failed series is flagged so a quiet result is not trusted."""
    summary = metrics_summary(
        [
            series("count: function errors", [], status="PartialData"),
            series("count: function throttles", [], status="Complete"),
        ]
    )

    assert summary["incomplete"] == ["count: function errors"]


@pytest.mark.unit
def test_the_metrics_summary_of_no_series_is_empty_but_well_formed():
    """No series at all still gives both keys."""
    assert metrics_summary([]) == {"metrics": [], "incomplete": []}
