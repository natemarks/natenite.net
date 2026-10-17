"""Behavior tests for the submit function's entry point.

Purpose:
- Send Function URL events in and assert on the HTTP response and on the
  records written, using an in-memory table and a fixed clock.
- No AWS credentials are needed.
"""

# pylint: disable=duplicate-code
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
from botocore.exceptions import ClientError

import handler
from definitions import parse_closes_at

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
DEFINITIONS["closing"] = dict(
    DEFINITIONS["poll1"], id="closing", closesAt="2026-10-16T12:00:00Z"
)


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
        now=lambda: open_time_for(poll),
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


def open_time_for(poll):
    """A moment when the poll is open: just before it closes, if it does.

    Polls close for real, so checks that submit to the polls in the
    repository must not assume they are still open at a fixed time.
    """
    closes_at = poll.get("closesAt")
    if closes_at is None:
        return NOW
    return parse_closes_at(closes_at) - timedelta(seconds=1)


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
        now=lambda: open_time_for(definitions[poll_id]),
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


@pytest.mark.unit
@pytest.mark.parametrize(
    "offset",
    [
        pytest.param(timedelta(0), id="at-the-closing-instant"),
        pytest.param(timedelta(seconds=1), id="one-second-after"),
        pytest.param(timedelta(days=30), id="long-after"),
    ],
)
def test_a_poll_closed_at_its_closing_time_answers_410(offset):
    """From the closing instant on, the poll is gone (HTTP 410)."""
    response, table = submit(
        {"pollId": "closing", "answers": {"q1": "a"}}, now=NOW + offset
    )

    assert response["statusCode"] == 410
    assert reason_of(response) == "poll_closed"
    assert not table.items


@pytest.mark.unit
def test_a_submission_just_before_the_closing_time_is_accepted():
    """One second before the closing instant the poll is still open."""
    response, table = submit(
        {"pollId": "closing", "answers": {"q1": "a"}},
        now=NOW - timedelta(seconds=1),
    )

    assert response["statusCode"] == 201
    assert len(table.items) == 1


@pytest.mark.unit
def test_a_poll_without_a_closing_time_never_closes():
    """No `closesAt` means the poll stays open indefinitely."""
    far_future = datetime(2100, 1, 1, tzinfo=timezone.utc)

    response, table = submit(
        {"pollId": "poll1", "answers": {"q1": "a"}}, now=far_future
    )

    assert response["statusCode"] == 201
    assert len(table.items) == 1


@pytest.mark.unit
def test_a_closed_poll_reports_closed_even_when_the_answers_are_wrong():
    """The closing check comes before the answer checks."""
    response, table = submit(
        {"pollId": "closing", "answers": {"q1": "zzz"}},
        now=NOW + timedelta(hours=1),
    )

    assert response["statusCode"] == 410
    assert reason_of(response) == "poll_closed"
    assert not table.items


def with_email(email, answers=None):
    """A valid poll1 submission carrying an email address."""
    return {
        "pollId": "poll1",
        "answers": answers or {"q1": "a"},
        "email": email,
    }


@pytest.mark.unit
def test_a_valid_email_is_stored_as_its_own_record_linked_to_the_response():
    """The address goes in a separate record that shares the response ID."""
    response, table = submit(with_email("reader@example.com"))

    assert response["statusCode"] == 201
    response_id = json.loads(response["body"])["responseId"]
    assert len(table.items) == 2
    stored_response, stored_email = table.items
    assert stored_response["sk"] == f"RESPONSE#{response_id}"
    assert "email" not in stored_response
    assert stored_email == {
        "pk": "POLL#poll1",
        "sk": f"EMAIL#{response_id}",
        "email": "reader@example.com",
        "submittedAt": "2026-10-16T12:00:00Z",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"pollId": "poll1", "answers": {"q1": "a"}}, id="no-field"
        ),
        pytest.param(with_email(""), id="empty"),
        pytest.param(with_email("   "), id="spaces"),
        pytest.param(with_email("\n\t "), id="newline-and-tab"),
    ],
)
def test_no_email_means_no_email_record(payload):
    """A missing or blank email stores the response and nothing else."""
    response, table = submit(payload)

    assert response["statusCode"] == 201
    assert len(table.items) == 1
    assert table.items[0]["sk"].startswith("RESPONSE#")


@pytest.mark.unit
@pytest.mark.parametrize(
    "email",
    [
        pytest.param("reader", id="no-at-sign"),
        pytest.param("reader@", id="nothing-after-the-at-sign"),
        pytest.param("@example.com", id="nothing-before-the-at-sign"),
        pytest.param("a@@example.com", id="two-at-signs"),
        pytest.param("a@b@example.com", id="at-sign-twice-apart"),
        pytest.param("reader@example", id="no-dot-in-the-domain"),
        pytest.param("reader@.com", id="domain-starts-with-a-dot"),
        pytest.param("reader@example.", id="domain-ends-with-a-dot"),
        pytest.param("reader@example..com", id="two-dots-in-a-row"),
        pytest.param("reader@example.com.", id="trailing-dot-after-the-tld"),
        pytest.param("read er@example.com", id="space-inside"),
        pytest.param("reader@exa mple.com", id="space-in-the-domain"),
        pytest.param("reader\n@example.com", id="newline-inside"),
        pytest.param(5, id="number"),
        pytest.param(None, id="null"),
        pytest.param(True, id="true"),
        pytest.param(["reader@example.com"], id="list"),
        pytest.param({"address": "reader@example.com"}, id="object"),
    ],
)
def test_a_malformed_email_is_rejected_and_nothing_is_stored(email):
    """An address that is not shaped like one is `invalid_email`."""
    response, table = submit(with_email(email))

    assert response["statusCode"] == 400
    assert reason_of(response) == "invalid_email"
    assert not table.items


@pytest.mark.unit
@pytest.mark.parametrize(
    "email",
    [
        pytest.param("reader@example.com", id="plain"),
        pytest.param(
            "first.last+tag@sub.example.co.uk", id="dots-plus-subdomain"
        ),
        pytest.param("  reader@example.com  ", id="surrounding-spaces"),
        pytest.param("Reader@Example.COM", id="mixed-case"),
        pytest.param("réader@exämple.com", id="non-ascii-letters"),
    ],
)
def test_ordinary_addresses_are_accepted(email):
    """Real-world shapes pass; surrounding spaces are trimmed, case kept."""
    response, table = submit(with_email(email))

    assert response["statusCode"] == 201
    assert table.items[1]["email"] == email.strip()


def address_of_length(length):
    """A well-shaped address with exactly `length` characters."""
    domain = "@example.com"
    return "a" * (length - len(domain)) + domain


@pytest.mark.unit
def test_an_email_is_capped_at_254_characters():
    """254 characters fit; spaces around the address are not counted."""
    for typed in (address_of_length(254), f"  {address_of_length(254)}  "):
        response, table = submit(with_email(typed))
        assert response["statusCode"] == 201
        assert table.items[1]["email"] == address_of_length(254)

    response, table = submit(with_email(address_of_length(255)))
    assert response["statusCode"] == 400
    assert reason_of(response) == "email_too_long"
    assert not table.items


@pytest.mark.unit
def test_an_overlong_email_is_reported_as_too_long_not_malformed():
    """Length is checked first, so a huge junk string says too long."""
    response, table = submit(with_email("x" * 5000))

    assert response["statusCode"] == 400
    assert reason_of(response) == "email_too_long"
    assert not table.items


class EmailWritesFail(FakeTable):  # pylint: disable=too-few-public-methods
    """A table whose writes of email records fail, as a real one can."""

    def put_item(self, Item):  # pylint: disable=invalid-name
        """Fail for email records, store everything else."""
        if Item["sk"].startswith("EMAIL#"):
            error = {"Error": {"Code": "InternalServerError", "Message": "x"}}
            raise ClientError(error, "PutItem")
        super().put_item(Item=Item)


@pytest.mark.unit
def test_a_failed_email_write_keeps_the_answers_and_reports_an_error():
    """The answers are the primary data: they stay, and the visitor is told."""
    address = "reader@example.com"
    response, table = submit(with_email(address), table=EmailWritesFail())

    assert response["statusCode"] == 500
    assert reason_of(response) == "email_not_stored"
    assert len(table.items) == 1
    assert table.items[0]["sk"].startswith("RESPONSE#")
    assert address not in response["body"]


@pytest.mark.unit
def test_an_email_address_never_reaches_logs_or_other_output(caplog, capsys):
    """Accepted, rejected and failed submissions leave no address behind."""
    caplog.set_level(logging.DEBUG)
    good = "needle.reader@example.com"
    bad = "needle.invalid@@example.com"
    too_long = "needle" + "x" * 300 + "@example.com"

    bodies = [
        submit(with_email(good))[0]["body"],
        submit(with_email(bad))[0]["body"],
        submit(with_email(too_long))[0]["body"],
        submit(with_email(good), table=EmailWritesFail())[0]["body"],
    ]

    out, err = capsys.readouterr()
    everything = caplog.text + out + err + "".join(bodies)
    assert "needle" not in everything


TOKEN = "0123456789abcdef0123456789abcdef"
# SHA-256 of TOKEN, computed independently with Python hashlib.
TOKEN_HASH = "3eb1bd439947eb762998e566ccc2e099c791118b2f40579cc4f7da2b5061b7f9"


def with_token(token, **extra):
    """A valid poll1 submission carrying a browser token."""
    return {
        "pollId": "poll1",
        "answers": {"q1": "a"},
        "browserToken": token,
        **extra,
    }


@pytest.mark.unit
def test_the_browser_token_is_stored_only_as_its_hash():
    """The record holds the hash; the raw token appears nowhere."""
    response, table = submit(with_token(TOKEN))

    assert response["statusCode"] == 201
    assert table.items[0]["browserTokenHash"] == TOKEN_HASH
    assert TOKEN not in json.dumps(table.items)
    assert TOKEN not in response["body"]


@pytest.mark.unit
def test_a_repeat_submission_with_the_same_token_is_accepted():
    """Soft dedupe: the server never rejects a repeat, it only records it."""
    table = FakeTable()

    first, _ = submit(with_token(TOKEN), table=table)
    second, _ = submit(
        with_token(TOKEN), table=table, now=NOW + timedelta(minutes=5)
    )

    assert first["statusCode"] == second["statusCode"] == 201
    assert len(table.items) == 2
    assert [i["browserTokenHash"] for i in table.items] == [TOKEN_HASH] * 2
    assert table.items[0]["sk"] != table.items[1]["sk"]


@pytest.mark.unit
def test_a_submission_without_a_token_is_accepted_and_has_no_hash():
    """Scripts and older cached pages send no token and still work."""
    response, table = submit({"pollId": "poll1", "answers": {"q1": "a"}})

    assert response["statusCode"] == 201
    assert "browserTokenHash" not in table.items[0]


@pytest.mark.unit
@pytest.mark.parametrize(
    "token",
    [
        pytest.param("", id="empty"),
        pytest.param("0123456789abcdef", id="too-short"),
        pytest.param(TOKEN + "0", id="too-long"),
        pytest.param(TOKEN.upper(), id="upper-case-hex"),
        pytest.param("g" * 32, id="not-hex"),
        pytest.param(" " + TOKEN[:31], id="leading-space"),
        pytest.param(TOKEN[:31] + "\n", id="trailing-newline"),
        pytest.param(5, id="number"),
        pytest.param(None, id="null"),
        pytest.param(True, id="true"),
        pytest.param([TOKEN], id="list"),
        pytest.param({"token": TOKEN}, id="object"),
    ],
)
def test_a_malformed_token_is_rejected_and_nothing_is_stored(token):
    """A token that is not 32 lower-case hex characters is `invalid_token`."""
    response, table = submit(with_token(token))

    assert response["statusCode"] == 400
    assert reason_of(response) == "invalid_token"
    assert not table.items
