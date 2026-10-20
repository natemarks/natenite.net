"""Behavior tests for the owner's poll dump script.

Purpose:
- Give the script a table that pages its results the way DynamoDB does and
  assert on what it writes: the responses, whether each visitor left an email,
  the address only when asked for, and the file's location and permissions.
"""

import io
import json
import stat
import subprocess
from decimal import Decimal

import pytest

import dump_poll
from config.helper import PROJECT_ROOT


class PagedTable:  # pylint: disable=too-few-public-methods
    """Table whose query returns two items per page, like a real one pages."""

    PAGE_SIZE = 2

    def __init__(self, items):
        self.items = items
        self.queries = 0

    def query(self, **kwargs):
        """Return one page of the items for the partition (and key prefix)."""
        self.queries += 1
        values = kwargs["ExpressionAttributeValues"]
        prefix = values.get(":prefix", "")
        matching = sorted(
            (
                item
                for item in self.items
                if item["pk"] == values[":pk"]
                and item["sk"].startswith(prefix)
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


def email_item(poll, number, address):
    """A stored email record, linked to a response by the shared ID."""
    return {
        "pk": f"POLL#{poll}",
        "sk": f"EMAIL#{number:03d}",
        "email": address,
        "submittedAt": "2026-10-16T12:00:00Z",
    }


def dump(table, include_emails=False, poll_id="poll1"):
    """Run the dump and return (parsed responses, raw text, warnings)."""
    warnings = io.StringIO()
    text = dump_poll.dump_poll(
        table, poll_id, include_emails=include_emails, warnings=warnings
    )
    return json.loads(text), text, warnings.getvalue()


@pytest.mark.unit
def test_dump_returns_one_polls_responses_in_order_across_pages():
    """All of one poll's responses come back, in order, nothing else."""
    table = PagedTable(
        [response_item("poll1", n) for n in (5, 1, 4, 2, 3)]
        + [response_item("poll2", 1)]
        + [email_item("poll1", 1, "a@example.com")]
    )

    dumped, _, _ = dump(table)

    assert [item["sk"] for item in dumped] == [
        f"RESPONSE#00{n}" for n in (1, 2, 3, 4, 5)
    ]
    assert table.queries == 3


@pytest.mark.unit
def test_by_default_each_response_says_whether_it_has_an_email_not_which():
    """The share who left an address is countable; no address is written."""
    table = PagedTable(
        [response_item("poll1", n) for n in (1, 2, 3)]
        + [email_item("poll1", 1, "first@example.com")]
        + [email_item("poll1", 3, "third@example.com")]
    )

    dumped, text, _ = dump(table)

    assert {item["sk"]: item["hasEmail"] for item in dumped} == {
        "RESPONSE#001": True,
        "RESPONSE#002": False,
        "RESPONSE#003": True,
    }
    assert all("email" not in item for item in dumped)
    assert "example.com" not in text


@pytest.mark.unit
def test_with_emails_each_response_carries_the_address_its_visitor_left():
    """Joined by response ID: others get null, other polls stay out."""
    table = PagedTable(
        [response_item("poll1", n) for n in (1, 2, 3)]
        + [email_item("poll1", 3, "third@example.com")]
        + [email_item("poll1", 1, "first@example.com")]
        # The same ID in another poll must not be joined to this poll
        + [response_item("poll2", 2)]
        + [email_item("poll2", 2, "other@example.com")]
    )

    dumped, text, warnings = dump(table, include_emails=True)

    assert {item["sk"]: item["email"] for item in dumped} == {
        "RESPONSE#001": "first@example.com",
        "RESPONSE#002": None,
        "RESPONSE#003": "third@example.com",
    }
    assert {item["sk"]: item["hasEmail"] for item in dumped} == {
        "RESPONSE#001": True,
        "RESPONSE#002": False,
        "RESPONSE#003": True,
    }
    assert "other@example.com" not in text
    assert warnings == ""


@pytest.mark.unit
@pytest.mark.parametrize("include_emails", [False, True])
def test_email_records_are_not_listed_as_responses(include_emails):
    """The output is the responses only, with the email information attached."""
    table = PagedTable(
        [response_item("poll1", 1), email_item("poll1", 1, "a@example.com")]
    )

    dumped, _, _ = dump(table, include_emails=include_emails)

    assert [item["sk"] for item in dumped] == ["RESPONSE#001"]
    assert "submittedAt" in dumped[0]


@pytest.mark.unit
@pytest.mark.parametrize("include_emails", [False, True])
def test_an_email_without_its_response_is_counted_but_never_printed(
    include_emails,
):
    """A response deleted on its own leaves its email: say so, no address."""
    table = PagedTable(
        [response_item("poll1", 1)]
        + [email_item("poll1", 7, "orphan@example.com")]
        + [email_item("poll1", 8, "orphan2@example.com")]
    )

    dumped, text, warnings = dump(table, include_emails=include_emails)

    assert [item["sk"] for item in dumped] == ["RESPONSE#001"]
    assert "2 email record(s) have no matching response" in warnings
    assert "example.com" not in warnings
    assert "orphan" not in text


@pytest.mark.unit
def test_dump_writes_numbers_as_plain_json_numbers():
    """DynamoDB's Decimal numbers do not leak into the output as strings."""
    table = PagedTable([response_item("poll1", 1)])

    dumped, _, _ = dump(table)

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
@pytest.mark.parametrize("include_emails", [False, True])
def test_dump_prints_every_record_with_its_keys_in_a_fixed_order(
    include_emails,
):
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

    first = dump(PagedTable([shuffled]), include_emails)[1]
    second = dump(PagedTable([in_another_order]), include_emails)[1]

    assert first == second
    record = json.loads(first)[0]
    assert list(record) == sorted(record)
    assert list(record["answers"]) == sorted(record["answers"])


@pytest.mark.unit
def test_a_poll_id_becomes_a_file_in_the_results_folder(tmp_path):
    """The file is named for the poll and lives in the results folder."""
    path = dump_poll.results_path("nov20267s-in-603", tmp_path)

    assert path == tmp_path / "nov20267s-in-603.json"


@pytest.mark.unit
@pytest.mark.parametrize(
    "poll_id",
    ["../escape", "a/b", "UPPER", "", "with space", "dots.json", ".hidden"],
)
def test_a_poll_id_that_is_not_a_plain_name_is_refused(poll_id, tmp_path):
    """No poll ID can point outside the results folder."""
    with pytest.raises(ValueError):
        dump_poll.results_path(poll_id, tmp_path)


@pytest.mark.unit
def test_results_are_readable_by_the_owner_only_and_replace_the_old_file(
    tmp_path,
):
    """The folder and file are private, and a new dump replaces the old."""
    path = tmp_path / "results" / "poll1.json"

    dump_poll.write_results(path, "first")
    dump_poll.write_results(path, "second")

    assert path.read_text(encoding="utf-8") == "second\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


@pytest.mark.unit
def test_a_file_that_was_looser_is_made_private_again(tmp_path):
    """An existing file with open permissions does not stay open."""
    path = tmp_path / "poll1.json"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o644)

    dump_poll.write_results(path, "new")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.unit
def test_the_command_writes_the_file_and_prints_only_a_summary(
    tmp_path, capsys
):
    """The responses go to the file; the terminal sees no answers or emails."""
    table = PagedTable(
        [response_item("poll1", n) for n in (1, 2)]
        + [email_item("poll1", 1, "first@example.com")]
    )

    dump_poll.main(["poll1"], table=table, results_dir=tmp_path)

    written = json.loads((tmp_path / "poll1.json").read_text(encoding="utf-8"))
    assert [item["hasEmail"] for item in written] == [True, False]
    assert all("email" not in item for item in written)
    out = capsys.readouterr().out
    assert "Wrote 2 response(s)" in out
    assert "poll1.json" in out
    assert "not included" in out
    assert "example.com" not in out
    assert '"answers"' not in out


@pytest.mark.unit
def test_with_the_emails_flag_the_file_holds_the_addresses(tmp_path, capsys):
    """Asking for emails puts them in the file, and still not on screen."""
    table = PagedTable(
        [response_item("poll1", 1), email_item("poll1", 1, "a@example.com")]
    )

    dump_poll.main(["poll1", "--emails"], table=table, results_dir=tmp_path)

    written = json.loads((tmp_path / "poll1.json").read_text(encoding="utf-8"))
    assert written[0]["email"] == "a@example.com"
    out = capsys.readouterr().out
    assert "included" in out and "not included" not in out
    assert "example.com" not in out


@pytest.mark.unit
def test_a_bad_poll_id_is_refused_and_nothing_is_written(tmp_path):
    """The command stops before touching the table or the disk."""
    with pytest.raises(SystemExit) as stopped:
        dump_poll.main(
            ["../escape"], table=PagedTable([]), results_dir=tmp_path
        )

    assert stopped.value.code == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.unit
def test_the_results_folder_is_ignored_by_git():
    """The results hold answers, and with emails, people: never committed."""
    inside = dump_poll.RESULTS_DIR / "nov20267s-in-603.json"

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(inside)],
        cwd=PROJECT_ROOT,
        check=False,
    )

    assert ignored.returncode == 0, ".polls-results/ must be in .gitignore"
