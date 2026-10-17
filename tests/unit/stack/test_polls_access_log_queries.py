#!/usr/bin/env python3
"""Tests for the Athena setup over the polls CloudFront access logs.

Purpose:
- The table reads the delivered JSON files in place, with partitions worked
  out from the date folders (no crawler, no repair command).
- Query results are kept briefly; the logs themselves for a year.
- The routine questions are saved as queries in a workgroup that caps cost.
"""

# pylint: disable=duplicate-code
import pytest

from tests.unit.stack.test_polls import polls_template

# The fields of a real delivered log line (the live check in slice 12).
LOG_FIELDS = [
    "date",
    "time",
    "x-edge-location",
    "sc-bytes",
    "c-ip",
    "cs-method",
    "cs(Host)",
    "cs-uri-stem",
    "sc-status",
    "cs(Referer)",
    "cs(User-Agent)",
    "cs-uri-query",
    "cs(Cookie)",
    "x-edge-result-type",
    "x-edge-request-id",
    "x-host-header",
    "cs-protocol",
    "cs-bytes",
    "time-taken",
    "x-forwarded-for",
    "ssl-protocol",
    "ssl-cipher",
    "x-edge-response-result-type",
    "cs-protocol-version",
    "fle-status",
    "fle-encrypted-fields",
    "c-port",
    "time-to-first-byte",
    "x-edge-detailed-result-type",
    "sc-content-type",
    "sc-content-len",
    "sc-range-start",
    "sc-range-end",
]


def _only(template, resource_type):
    """The single resource of a type: (logical id, body)."""
    found = template.find_resources(resource_type)
    assert len(found) == 1, resource_type
    return found.popitem()


def _table(template):
    """The log table's properties."""
    return _only(template, "AWS::Glue::Table")[1]["Properties"]


@pytest.mark.unit
def test_results_expire_after_a_month_and_the_logs_after_a_year():
    """Two rules, each limited to its own folder of the log bucket."""
    template = polls_template()
    buckets = [
        body
        for body in template.find_resources("AWS::S3::Bucket").values()
        if "LifecycleConfiguration" in body["Properties"]
    ]
    (bucket,) = buckets
    rules = bucket["Properties"]["LifecycleConfiguration"]["Rules"]
    assert sorted(
        (rule["Prefix"], rule["ExpirationInDays"], rule["Status"])
        for rule in rules
    ) == [
        ("athena-results/", 30, "Enabled"),
        ("cloudfront/polls/", 365, "Enabled"),
    ]


@pytest.mark.unit
def test_the_table_reads_the_delivered_json_where_it_lands():
    """An external table over the log prefix, read as JSON."""
    template = polls_template()
    table = _table(template)["TableInput"]
    assert table["TableType"] == "EXTERNAL_TABLE"
    storage = table["StorageDescriptor"]
    assert "/cloudfront/polls/" in str(storage["Location"])
    assert "json" in storage["SerdeInfo"]["SerializationLibrary"].lower()
    assert [key["Name"] for key in table["PartitionKeys"]] == [
        "year",
        "month",
        "day",
    ]


@pytest.mark.unit
def test_every_log_field_is_a_column_that_maps_back_to_its_json_name():
    """Athena names can't hold - or (); the SerDe maps each back."""
    template = polls_template()
    storage = _table(template)["TableInput"]["StorageDescriptor"]
    mapping = {
        key.removeprefix("mapping."): value
        for key, value in storage["SerdeInfo"]["Parameters"].items()
        if key.startswith("mapping.")
    }
    columns = [column["Name"] for column in storage["Columns"]]

    assert sorted(mapping.values()) == sorted(LOG_FIELDS)
    assert sorted(columns) == sorted(mapping)
    assert mapping["c_ip"] == "c-ip"
    assert mapping["cs_host"] == "cs(Host)"
    assert mapping["cs_user_agent"] == "cs(User-Agent)"
    assert mapping["x_edge_detailed_result_type"] == (
        "x-edge-detailed-result-type"
    )


@pytest.mark.unit
def test_partitions_are_worked_out_from_the_date_folders():
    """Partition projection, so no crawler or repair command is needed."""
    template = polls_template()
    params = _table(template)["TableInput"]["Parameters"]
    # Every projected folder is listed in S3 when a query is planned, so the
    # count must stay small: a hang at 187,000 (21 years of hours) taught this.
    count = 1
    for part in ("year", "month", "day"):
        low, high = params[f"projection.{part}.range"].split(",")
        count *= int(high) - int(low) + 1
    assert count <= 2000
    assert params["projection.enabled"] == "true"
    for part in ("year", "month", "day"):
        assert params[f"projection.{part}.type"] == "integer"
    assert params["projection.month.digits"] == "2"
    assert "hour" not in str(params)
    assert "year=${year}/month=${month}/day=${day}/" in str(
        params["storage.location.template"]
    )


@pytest.mark.unit
def test_the_workgroup_keeps_results_in_the_expiring_folder_and_caps_scans():
    """Settings are enforced so a query can't write elsewhere."""
    template = polls_template()
    _, group = _only(template, "AWS::Athena::WorkGroup")
    config = group["Properties"]["WorkGroupConfiguration"]
    assert config["EnforceWorkGroupConfiguration"] is True
    assert "/athena-results/" in str(
        config["ResultConfiguration"]["OutputLocation"]
    )
    assert 0 < config["BytesScannedCutoffPerQuery"] <= 10 * 1024**3


@pytest.mark.unit
def test_the_routine_questions_are_saved_in_the_workgroup():
    """Errors by day, top client addresses, and 403 / 429 responses."""
    template = polls_template()
    group_id, _ = _only(template, "AWS::Athena::WorkGroup")
    queries = {
        body["Properties"]["Name"]: body["Properties"]
        for body in template.find_resources("AWS::Athena::NamedQuery").values()
    }
    assert sorted(queries) == [
        "polls/blocked-and-throttled",
        "polls/errors-by-day",
        "polls/top-client-addresses",
    ]
    for name, query in queries.items():
        assert query["WorkGroup"] == {"Ref": group_id}, name
        assert "cloudfront_logs" in query["QueryString"], name
        # Limits the partitions read rather than scanning every file
        assert "year" in query["QueryString"], name
    assert "403" in queries["polls/blocked-and-throttled"]["QueryString"]
    assert "429" in queries["polls/blocked-and-throttled"]["QueryString"]
    assert "c_ip" in queries["polls/top-client-addresses"]["QueryString"]


@pytest.mark.unit
def test_the_saved_queries_are_ready_to_run_in_the_console():
    """The day count is filled in for the console; nothing is left to edit."""
    template = polls_template()
    queries = {
        body["Properties"]["Name"]: body["Properties"]["QueryString"]
        for body in template.find_resources("AWS::Athena::NamedQuery").values()
    }
    for name, sql in queries.items():
        assert "{" not in sql and "}" not in sql, name
    assert "interval '30' day" in queries["polls/errors-by-day"]
    assert "interval '7' day" in queries["polls/top-client-addresses"]
