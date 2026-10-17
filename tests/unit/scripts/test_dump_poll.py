"""Behavior tests for the owner's poll dump script.

Purpose:
- Give the script a table that pages its results the way DynamoDB does and
  assert on the JSON it produces.
"""

import json
from decimal import Decimal

import pytest

import dump_poll


class PagedTable:  # pylint: disable=too-few-public-methods
    """Table whose query returns two items per page, like a real one pages."""

    PAGE_SIZE = 2

    def __init__(self, items):
        self.items = items
        self.queries = 0

    def query(self, **kwargs):
        """Return one page of the items for the partition and key prefix."""
        self.queries += 1
        values = kwargs["ExpressionAttributeValues"]
        matching = sorted(
            (
                item
                for item in self.items
                if item["pk"] == values[":pk"]
                and item["sk"].startswith(values[":prefix"])
            ),
            key=lambda item: item["sk"],
        )
        start = kwargs.get("ExclusiveStartKey")
        if start:
            matching = [i for i in matching if i["sk"] > start["sk"]]
        page = matching[: self.PAGE_SIZE]
        result = {"Items": page}
        if len(matching) > self.PAGE_SIZE:
            result["LastEvaluatedKey"] = {
                "pk": page[-1]["pk"],
                "sk": page[-1]["sk"],
            }
        return result


def response_item(poll, number):
    """A stored response record, as DynamoDB returns it."""
    return {
        "pk": f"POLL#{poll}",
        "sk": f"RESPONSE#{number:03d}",
        "answers": {"q1": "a"},
        "submittedAt": "2026-10-16T12:00:00Z",
        "pollVersion": Decimal(3),
    }


@pytest.mark.unit
def test_dump_returns_one_polls_responses_in_order_across_pages():
    """All of one poll's responses come back, in order, nothing else."""
    table = PagedTable(
        [response_item("poll1", n) for n in (5, 1, 4, 2, 3)]
        + [response_item("poll2", 1)]
        + [{"pk": "POLL#poll1", "sk": "EMAIL#001", "email": "a@example.com"}]
    )

    dumped = json.loads(dump_poll.dump_poll(table, "poll1"))

    assert [item["sk"] for item in dumped] == [
        f"RESPONSE#00{n}" for n in (1, 2, 3, 4, 5)
    ]
    assert table.queries == 3


@pytest.mark.unit
def test_dump_writes_numbers_as_plain_json_numbers():
    """DynamoDB's Decimal numbers do not leak into the output as strings."""
    table = PagedTable([response_item("poll1", 1)])

    dumped = json.loads(dump_poll.dump_poll(table, "poll1"))

    assert dumped[0]["pollVersion"] == 3
    assert isinstance(dumped[0]["pollVersion"], int)


class RecordingResource:  # pylint: disable=too-few-public-methods
    """Stand-in for boto3.resource that records how it was called."""

    def __init__(self):
        self.calls = []

    def __call__(self, service, **kwargs):
        self.calls.append((service, kwargs))
        return self

    def Table(self, name):  # pylint: disable=invalid-name
        """Return the table name asked for, so the test can see it."""
        return f"table:{name}"


@pytest.mark.unit
def test_script_opens_the_environments_table_in_its_configured_region():
    """The script must not depend on an ambient AWS region setting."""
    resource = RecordingResource()

    table = dump_poll.open_table("production", resource=resource)

    assert table == "table:natenite-production-polls-responses"
    assert resource.calls == [("dynamodb", {"region_name": "us-east-1"})]


@pytest.mark.unit
def test_dump_prints_every_record_with_its_keys_in_a_fixed_order():
    """DynamoDB returns attributes in no fixed order; the dump must not."""
    shuffled = {
        "sk": "RESPONSE#001",
        "answers": {"q2": "b", "q1": "a"},
        "pollVersion": Decimal(1),
        "pk": "POLL#poll1",
        "submittedAt": "2026-10-17T00:00:00Z",
    }
    in_another_order = dict(reversed(list(shuffled.items())))
    in_another_order["answers"] = {"q1": "a", "q2": "b"}

    first = dump_poll.dump_poll(PagedTable([shuffled]), "poll1")
    second = dump_poll.dump_poll(PagedTable([in_another_order]), "poll1")

    assert first == second
    record = json.loads(first)[0]
    assert list(record) == sorted(record)
    assert list(record["answers"]) == sorted(record["answers"])
