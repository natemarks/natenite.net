"""Behavior tests for the submit function's entry point.

Purpose:
- Send Function URL events in and assert on the HTTP response and on the
  records written, using an in-memory table and a fixed clock.
- No AWS credentials are needed.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import handler

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

DEFINITIONS = {
    "poll1": {
        "id": "poll1",
        "title": "Example poll",
        "version": 3,
        "questions": [
            {
                "id": "q1",
                "type": "single",
                "prompt": "Which option do you prefer?",
                "options": [
                    {"id": "a", "label": "Option A"},
                    {"id": "b", "label": "Option B"},
                ],
            }
        ],
    }
}


class FakeTable:  # pylint: disable=too-few-public-methods
    """In-memory stand-in for the DynamoDB table."""

    def __init__(self):
        self.items = []

    def put_item(self, Item):  # pylint: disable=invalid-name
        """Record the item as the real table's put_item would store it."""
        self.items.append(Item)


def post_event(payload, method="POST", path="/submit"):
    """Build a Function URL (payload v2) event carrying a JSON body."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return {
        "version": "2.0",
        "rawPath": path,
        "headers": {"content-type": "application/json"},
        "requestContext": {"http": {"method": method, "path": path}},
        "body": body,
        "isBase64Encoded": False,
    }


def submit(payload, table=None, now=NOW, **event_kwargs):
    """Call the entry point and return (response, table)."""
    table = FakeTable() if table is None else table
    response = handler.handle(
        post_event(payload, **event_kwargs),
        table=table,
        definitions=DEFINITIONS,
        now=lambda: now,
    )
    return response, table


@pytest.mark.unit
def test_valid_submission_is_stored_and_acknowledged():
    """A valid single-choice submission writes one response record."""
    response, table = submit({"pollId": "poll1", "answers": {"q1": "a"}})

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert len(table.items) == 1
    item = table.items[0]
    assert item["pk"] == "POLL#poll1"
    assert item["sk"] == f"RESPONSE#{body['responseId']}"
    assert item["answers"] == {"q1": "a"}
    assert item["submittedAt"] == "2026-10-16T12:00:00Z"
    assert item["pollVersion"] == 3


@pytest.mark.unit
def test_response_ids_sort_in_submission_order():
    """Sort keys come back in the order the responses were submitted."""
    table = FakeTable()
    for offset_ms in (0, 3, 5, 9, 250):
        submit(
            {"pollId": "poll1", "answers": {"q1": "a"}},
            table=table,
            now=NOW + timedelta(milliseconds=offset_ms),
        )

    sort_keys = [item["sk"] for item in table.items]
    assert sort_keys == sorted(sort_keys)
    assert len(set(sort_keys)) == 5


@pytest.mark.unit
def test_unknown_option_is_rejected_and_not_stored():
    """An option that the question does not offer is a client error."""
    response, table = submit({"pollId": "poll1", "answers": {"q1": "zzz"}})

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["reason"] == "unknown_option"
    assert not table.items


@pytest.mark.unit
def test_missing_answer_is_rejected_and_not_stored():
    """Every question in this slice is required."""
    response, table = submit({"pollId": "poll1", "answers": {}})

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["reason"] == "missing_answer"
    assert not table.items


@pytest.mark.unit
def test_answer_to_unknown_question_is_rejected_and_not_stored():
    """Answers may only be given to the poll's own questions."""
    response, table = submit(
        {"pollId": "poll1", "answers": {"q1": "a", "q9": "a"}}
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["reason"] == "unknown_question"
    assert not table.items


@pytest.mark.unit
def test_unknown_poll_is_not_found():
    """A poll that has no definition cannot take responses."""
    response, table = submit({"pollId": "nope", "answers": {"q1": "a"}})

    assert response["statusCode"] == 404
    assert json.loads(response["body"])["reason"] == "unknown_poll"
    assert not table.items


def padded_body(size_bytes):
    """A valid submission padded with trailing spaces to an exact size."""
    body = json.dumps({"pollId": "poll1", "answers": {"q1": "a"}})
    return body + " " * (size_bytes - len(body.encode("utf-8")))


@pytest.mark.unit
def test_body_over_six_kilobytes_is_rejected_and_not_stored():
    """6,144 bytes is accepted; one byte more is payload-too-large."""
    response, table = submit(padded_body(6144))
    assert response["statusCode"] == 201
    assert len(table.items) == 1

    response, table = submit(padded_body(6145))
    assert response["statusCode"] == 413
    assert json.loads(response["body"])["reason"] == "payload_too_large"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize(
    "body, reason",
    [
        pytest.param("not json{", "invalid_json", id="unparseable"),
        pytest.param("[]", "invalid_request", id="not-an-object"),
        pytest.param('{"answers": {}}', "invalid_request", id="no-poll-id"),
        pytest.param(
            '{"pollId": 5, "answers": {}}', "invalid_request", id="poll-id-int"
        ),
        pytest.param(
            '{"pollId": "poll1"}', "invalid_request", id="no-answers"
        ),
        pytest.param(
            '{"pollId": "poll1", "answers": []}',
            "invalid_request",
            id="answers-list",
        ),
        pytest.param(
            '{"pollId": "poll1", "answers": {"q1": ["a"]}}',
            "invalid_request",
            id="answer-not-a-string",
        ),
    ],
)
def test_malformed_requests_get_a_client_error_not_a_crash(body, reason):
    """Anything that is not a well-formed submission is a clean 400."""
    response, table = submit(body)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["reason"] == reason
    assert not table.items


@pytest.mark.unit
def test_only_post_to_submit_is_served():
    """Other methods are 405 and other paths are 404; nothing is stored."""
    payload = {"pollId": "poll1", "answers": {"q1": "a"}}

    response, table = submit(payload, method="GET")
    assert response["statusCode"] == 405
    assert json.loads(response["body"])["reason"] == "method_not_allowed"
    assert not table.items

    response, table = submit(payload, path="/other")
    assert response["statusCode"] == 404
    assert json.loads(response["body"])["reason"] == "not_found"
    assert not table.items


@pytest.mark.unit
def test_post_without_a_body_is_a_client_error():
    """An event with no body at all is treated as unparseable, not a crash."""
    event = post_event({"pollId": "poll1", "answers": {"q1": "a"}})
    del event["body"]
    table = FakeTable()

    response = handler.handle(
        event, table=table, definitions=DEFINITIONS, now=lambda: NOW
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["reason"] == "invalid_json"
    assert not table.items


@pytest.mark.unit
def test_definitions_are_loaded_by_poll_id(tmp_path):
    """Every JSON file in the directory becomes a poll, keyed by its ID."""
    (tmp_path / "first.json").write_text(json.dumps(DEFINITIONS["poll1"]))
    other = dict(DEFINITIONS["poll1"], id="poll2", title="Another poll")
    (tmp_path / "second.json").write_text(json.dumps(other))
    (tmp_path / "notes.txt").write_text("not a poll")

    loaded = handler.load_definitions(tmp_path)

    assert sorted(loaded) == ["poll1", "poll2"]
    assert loaded["poll2"]["title"] == "Another poll"


@pytest.mark.unit
def test_bundled_definitions_accept_a_valid_submission():
    """The definitions shipped with the function can take a response."""
    definitions = handler.load_definitions(handler.BUNDLED_DEFINITIONS_DIR)
    poll = definitions["poll1"]
    answers = {
        question["id"]: question["options"][0]["id"]
        for question in poll["questions"]
    }
    table = FakeTable()

    response = handler.handle(
        post_event({"pollId": "poll1", "answers": answers}),
        table=table,
        definitions=definitions,
        now=lambda: NOW,
    )

    assert response["statusCode"] == 201
    assert table.items[0]["pollVersion"] == poll["version"]
