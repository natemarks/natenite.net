"""Behavior tests for the owner's email maintenance script.

Purpose:
- Check which email records the script finds and deletes, against a table
  that pages its scans the way DynamoDB does.
- Check that it never touches responses and never reports an address.
"""

from datetime import datetime, timedelta, timezone

import pytest

import manage_emails

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)


class ScanTable:
    """In-memory table with a paged scan and delete_item."""

    PAGE_SIZE = 2

    def __init__(self, items):
        self.items = list(items)
        self.deleted = []

    def scan(self, **kwargs):
        """Return one page of the items whose sort key has the prefix."""
        prefix = kwargs["ExpressionAttributeValues"][":prefix"]
        matching = sorted(
            (i for i in self.items if i["sk"].startswith(prefix)),
            key=lambda i: (i["pk"], i["sk"]),
        )
        start = kwargs.get("ExclusiveStartKey")
        if start:
            matching = [
                i
                for i in matching
                if (i["pk"], i["sk"]) > (start["pk"], start["sk"])
            ]
        page = matching[: self.PAGE_SIZE]
        result = {"Items": page}
        if len(matching) > self.PAGE_SIZE:
            last = page[-1]
            result["LastEvaluatedKey"] = {"pk": last["pk"], "sk": last["sk"]}
        return result

    def delete_item(self, Key):  # pylint: disable=invalid-name
        """Remove the item with this key."""
        self.deleted.append((Key["pk"], Key["sk"]))
        self.items = [
            i
            for i in self.items
            if (i["pk"], i["sk"]) != (Key["pk"], Key["sk"])
        ]


def stamp(days_ago):
    """A submittedAt string for a record made `days_ago` days before NOW."""
    when = NOW - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def email_record(poll, number, address, days_ago):
    """A stored email record."""
    return {
        "pk": f"POLL#{poll}",
        "sk": f"EMAIL#{number:03d}",
        "email": address,
        "submittedAt": stamp(days_ago),
    }


def response_record(poll, number, days_ago):
    """A stored response record, which the script must never touch."""
    return {
        "pk": f"POLL#{poll}",
        "sk": f"RESPONSE#{number:03d}",
        "answers": {"q1": "a"},
        "submittedAt": stamp(days_ago),
        "pollVersion": 1,
    }


def table_with_mixed_ages():
    """Old and young emails across two polls, plus responses."""
    return ScanTable(
        [
            email_record("poll1", 1, "old1@example.com", 400),
            email_record("poll1", 2, "young@example.com", 10),
            email_record("poll2", 3, "old2@example.com", 366),
            email_record("poll2", 4, "boundary@example.com", 365),
            response_record("poll1", 1, 400),
            response_record("poll2", 3, 366),
        ]
    )


@pytest.mark.unit
def test_purge_is_a_dry_run_unless_told_to_apply():
    """By default it reports what is older than N days and deletes nothing."""
    table = table_with_mixed_ages()

    found = manage_emails.purge_older_than(table, days=365, now=NOW)

    assert [(r["pk"], r["sk"]) for r in found] == [
        ("POLL#poll1", "EMAIL#001"),
        ("POLL#poll2", "EMAIL#003"),
    ]
    assert not table.deleted


@pytest.mark.unit
def test_purge_with_apply_deletes_only_older_email_records():
    """Older emails go; the boundary, young emails and responses stay."""
    table = table_with_mixed_ages()

    found = manage_emails.purge_older_than(
        table, days=365, now=NOW, apply=True
    )

    assert sorted(table.deleted) == [
        ("POLL#poll1", "EMAIL#001"),
        ("POLL#poll2", "EMAIL#003"),
    ]
    assert len(found) == 2
    remaining = sorted(i["sk"] for i in table.items)
    assert remaining == [
        "EMAIL#002",
        "EMAIL#004",
        "RESPONSE#001",
        "RESPONSE#003",
    ]


@pytest.mark.unit
def test_purge_never_reports_an_address():
    """What the script prints has keys and dates, not addresses."""
    found = manage_emails.purge_older_than(table_with_mixed_ages(), 365, NOW)

    assert all("email" not in record for record in found)
    assert "@" not in repr(found)


@pytest.mark.unit
def test_purge_follows_every_page_of_the_scan():
    """More matches than one page holds are all found."""
    table = ScanTable(
        [
            email_record("poll1", n, f"user{n}@example.com", 500)
            for n in range(1, 6)
        ]
    )

    found = manage_emails.purge_older_than(
        table, days=365, now=NOW, apply=True
    )

    assert len(found) == 5
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize("days", [-1, 1.5, "30", None])
def test_purge_refuses_a_nonsensical_age(days):
    """A negative or non-integer age is an error, never a mass delete."""
    table = table_with_mixed_ages()

    with pytest.raises(ValueError):
        manage_emails.purge_older_than(table, days=days, now=NOW, apply=True)

    assert not table.deleted


def table_with_one_person_twice():
    """The same person on two polls, with different capitalization."""
    return ScanTable(
        [
            email_record("poll1", 1, "Reader@Example.com", 30),
            email_record("poll2", 2, "reader@example.COM", 20),
            email_record("poll2", 3, "someone.else@example.com", 10),
            response_record("poll1", 1, 30),
            response_record("poll2", 2, 20),
        ]
    )


@pytest.mark.unit
def test_delete_by_email_is_a_dry_run_unless_told_to_apply():
    """It finds every record for the address, ignoring case, deleting none."""
    table = table_with_one_person_twice()

    found = manage_emails.delete_by_email(table, "  READER@example.com ")

    assert [(r["pk"], r["sk"]) for r in found] == [
        ("POLL#poll1", "EMAIL#001"),
        ("POLL#poll2", "EMAIL#002"),
    ]
    assert not table.deleted
    assert "@" not in repr(found)


@pytest.mark.unit
def test_delete_by_email_with_apply_removes_only_that_persons_records():
    """Other people's emails and all responses are left alone."""
    table = table_with_one_person_twice()

    manage_emails.delete_by_email(table, "reader@example.com", apply=True)

    assert sorted(i["sk"] for i in table.items) == [
        "EMAIL#003",
        "RESPONSE#001",
        "RESPONSE#002",
    ]


@pytest.mark.unit
def test_delete_by_email_for_an_unknown_address_finds_nothing():
    """No match is an empty report, not an error."""
    table = table_with_one_person_twice()

    assert (
        manage_emails.delete_by_email(table, "nobody@example.com", True) == []
    )
    assert not table.deleted


@pytest.mark.unit
@pytest.mark.parametrize("address", ["", "   ", None, 5])
def test_delete_by_email_refuses_a_blank_address(address):
    """An empty address must never match (and delete) everything."""
    table = table_with_one_person_twice()

    with pytest.raises(ValueError):
        manage_emails.delete_by_email(table, address, apply=True)

    assert not table.deleted


@pytest.mark.unit
def test_command_line_purge_reports_a_dry_run_and_prints_no_address(capsys):
    """Without --yes nothing is deleted, and the output says so."""
    table = table_with_mixed_ages()

    manage_emails.main(
        ["purge", "--older-than-days", "365"], table=table, now=NOW
    )

    out = capsys.readouterr().out
    assert not table.deleted
    assert "Dry run" in out
    assert "2 record(s)" in out
    assert "EMAIL#001" in out
    assert "@" not in out


@pytest.mark.unit
def test_command_line_purge_with_yes_deletes_and_says_how_many(capsys):
    """--yes deletes, and the output says what was deleted."""
    table = table_with_mixed_ages()

    manage_emails.main(
        ["purge", "--older-than-days", "365", "--yes"], table=table, now=NOW
    )

    out = capsys.readouterr().out
    assert len(table.deleted) == 2
    assert "Deleted 2 record(s)" in out
    assert "@" not in out


@pytest.mark.unit
def test_command_line_delete_by_email(capsys):
    """The delete command works the same way, per address."""
    table = table_with_one_person_twice()

    manage_emails.main(
        ["delete", "--email", "reader@example.com"], table=table, now=NOW
    )
    assert not table.deleted
    assert "Dry run" in capsys.readouterr().out

    manage_emails.main(
        ["delete", "--email", "reader@example.com", "--yes"],
        table=table,
        now=NOW,
    )
    assert len(table.deleted) == 2
    assert "Deleted 2 record(s)" in capsys.readouterr().out


@pytest.mark.unit
def test_command_line_rejects_a_non_numeric_age():
    """Bad input stops with a usage error before anything is touched."""
    table = table_with_mixed_ages()

    with pytest.raises(SystemExit):
        manage_emails.main(
            ["purge", "--older-than-days", "soon", "--yes"],
            table=table,
            now=NOW,
        )

    assert not table.deleted
