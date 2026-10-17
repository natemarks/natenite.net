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


MIXED_POLL = {
    "id": "poll2",
    "title": "Poll with every question type",
    "version": 1,
    "questions": [
        {
            "id": "q1",
            "type": "single",
            "prompt": "Pick one",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        {
            "id": "q2",
            "type": "multi",
            "prompt": "Pick any",
            "options": [
                {"id": "x", "label": "X"},
                {"id": "y", "label": "Y"},
                {"id": "z", "label": "Z"},
            ],
        },
        {
            "id": "q3",
            "type": "rating",
            "prompt": "Rate it",
            "min": 1,
            "max": 5,
        },
        {"id": "q4", "type": "text", "prompt": "Anything else?"},
    ],
}
DEFINITIONS["poll2"] = MIXED_POLL


class FakeTable:  # pylint: disable=too-few-public-methods
    """In-memory stand-in for the DynamoDB table."""

    def __init__(self):
        self.items = []

    def put_item(self, Item):  # pylint: disable=invalid-name
        """Record the item as the real table's put_item would store it."""
        self.items.append(Item)


def post_event(payload, method="POST", path="/submit"):
    """Build a Function URL (payload v2) event carrying a JSON body."""
    # ensure_ascii=False matches a browser's JSON.stringify, which does not
    # escape non-ASCII characters.
    body = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False)
    )
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
            "invalid_answer",
            id="list-for-a-single-choice-question",
        ),
        pytest.param(
            '{"pollId": "poll1", "answers": {"q1": 5}}',
            "invalid_answer",
            id="number-for-a-single-choice-question",
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


@pytest.mark.unit
def test_multiple_choice_and_rating_answers_are_stored_in_their_shapes():
    """A list of option IDs and an integer are stored as given."""
    response, table = submit(
        {
            "pollId": "poll2",
            "answers": {"q1": "a", "q2": ["x", "z"], "q3": 4, "q4": "Ok"},
        }
    )

    assert response["statusCode"] == 201
    assert table.items[0]["answers"] == {
        "q1": "a",
        "q2": ["x", "z"],
        "q3": 4,
        "q4": "Ok",
    }


def mixed_answers(**overrides):
    """A valid answer set for the mixed poll, with some answers replaced."""
    answers = {"q1": "a", "q2": ["x"], "q3": 3, "q4": "Hello"}
    answers.update(overrides)
    return {"pollId": "poll2", "answers": answers}


def reason_of(response):
    """The machine-readable reason in an error response."""
    return json.loads(response["body"])["reason"]


@pytest.mark.unit
def test_multiple_choice_with_an_unknown_option_is_rejected():
    """Every selected option must be one the question offers."""
    response, table = submit(mixed_answers(q2=["x", "nope"]))

    assert response["statusCode"] == 400
    assert reason_of(response) == "unknown_option"
    assert not table.items


@pytest.mark.unit
def test_multiple_choice_with_a_repeated_option_is_rejected():
    """An option can be chosen only once."""
    response, table = submit(mixed_answers(q2=["x", "y", "x"]))

    assert response["statusCode"] == 400
    assert reason_of(response) == "duplicate_option"
    assert not table.items


@pytest.mark.unit
def test_multiple_choice_with_no_selection_counts_as_unanswered():
    """Every question is required, so an empty selection is missing."""
    response, table = submit(mixed_answers(q2=[]))

    assert response["statusCode"] == 400
    assert reason_of(response) == "missing_answer"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("x", id="bare-string"),
        pytest.param("xy", id="string-that-spells-two-options"),
        pytest.param([1], id="list-of-numbers"),
        pytest.param([["x"]], id="nested-list"),
        pytest.param(None, id="null"),
        pytest.param({"x": 1}, id="object"),
        pytest.param(5, id="number"),
    ],
)
def test_multiple_choice_needs_a_list_of_option_ids(value):
    """Anything other than a list of strings is an invalid answer."""
    response, table = submit(mixed_answers(q2=value))

    assert response["statusCode"] == 400
    assert reason_of(response) == "invalid_answer"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize("rating", [1, 3, 5])
def test_ratings_within_bounds_are_accepted(rating):
    """The bounds are inclusive."""
    response, table = submit(mixed_answers(q3=rating))

    assert response["statusCode"] == 201
    assert table.items[0]["answers"]["q3"] == rating


@pytest.mark.unit
@pytest.mark.parametrize("rating", [0, 6, -1, 100])
def test_ratings_outside_bounds_are_rejected(rating):
    """A rating outside the question's min and max is out of range."""
    response, table = submit(mixed_answers(q3=rating))

    assert response["statusCode"] == 400
    assert reason_of(response) == "rating_out_of_range"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(3.5, id="fraction"),
        pytest.param(3.0, id="whole-number-written-as-a-float"),
        pytest.param("4", id="string"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param(None, id="null"),
        pytest.param([3], id="list"),
        pytest.param({"v": 3}, id="object"),
    ],
)
def test_a_rating_must_be_a_whole_number(value):
    """Only a JSON integer is a rating; true counts as invalid, not as 1."""
    response, table = submit(mixed_answers(q3=value))

    assert response["statusCode"] == 400
    assert reason_of(response) == "invalid_answer"
    assert not table.items


def valid_answers_for(poll):
    """One valid answer per question, built from the question's own shape."""
    answers = {}
    for question in poll["questions"]:
        if question["type"] == "multi":
            answers[question["id"]] = [question["options"][0]["id"]]
        elif question["type"] == "rating":
            answers[question["id"]] = question["min"]
        elif question["type"] == "text":
            answers[question["id"]] = "A short free-text answer"
        else:
            answers[question["id"]] = question["options"][0]["id"]
    return answers


@pytest.mark.unit
@pytest.mark.parametrize(
    "poll_id",
    sorted(handler.load_definitions(handler.BUNDLED_DEFINITIONS_DIR)),
)
def test_every_bundled_poll_accepts_a_valid_submission(poll_id):
    """Each poll shipped with the function can take a response."""
    definitions = handler.load_definitions(handler.BUNDLED_DEFINITIONS_DIR)
    table = FakeTable()

    response = handler.handle(
        post_event(
            {
                "pollId": poll_id,
                "answers": valid_answers_for(definitions[poll_id]),
            }
        ),
        table=table,
        definitions=definitions,
        now=lambda: NOW,
    )

    assert response["statusCode"] == 201
    assert len(table.items) == 1


@pytest.mark.unit
def test_free_text_is_stored_exactly_as_typed():
    """Nothing is trimmed or changed in a free-text answer."""
    typed = "  two lines\nof text  "

    response, table = submit(mixed_answers(q4=typed))

    assert response["statusCode"] == 201
    assert table.items[0]["answers"]["q4"] == typed


@pytest.mark.unit
@pytest.mark.parametrize(
    "blank",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="spaces"),
        pytest.param("\n\t \r\n", id="newlines-and-tabs"),
    ],
)
def test_a_blank_free_text_answer_counts_as_unanswered(blank):
    """Free text is required, and whitespace alone is not an answer."""
    response, table = submit(mixed_answers(q4=blank))

    assert response["statusCode"] == 400
    assert reason_of(response) == "missing_answer"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize(
    "character",
    [
        pytest.param("x", id="ascii"),
        pytest.param("é", id="two-byte-character"),
        pytest.param("\U0001f600", id="emoji-outside-the-bmp"),
    ],
)
def test_free_text_is_capped_at_500_characters(character):
    """500 characters are accepted and 501 are not, whatever their bytes."""
    response, table = submit(mixed_answers(q4=character * 500))
    assert response["statusCode"] == 201
    assert len(table.items) == 1

    response, table = submit(mixed_answers(q4=character * 501))
    assert response["statusCode"] == 400
    assert reason_of(response) == "answer_too_long"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(5, id="number"),
        pytest.param(None, id="null"),
        pytest.param(["hello"], id="list"),
        pytest.param({"text": "hello"}, id="object"),
        pytest.param(True, id="true"),
    ],
)
def test_free_text_must_be_a_string(value):
    """Anything other than a string is an invalid answer."""
    response, table = submit(mixed_answers(q4=value))

    assert response["statusCode"] == 400
    assert reason_of(response) == "invalid_answer"
    assert not table.items
