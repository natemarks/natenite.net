"""Submit function: validate a poll response and store it.

Purpose:
- Accept a poll response posted through CloudFront as a Lambda Function URL
  event, check it against the poll's definition, and store it.

Flow:
- `handle` is the testable entry point: the table, the poll definitions and
  the clock are passed in.
- `handler` is the deployed entry point that supplies the real ones.
"""

import functools
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

import boto3

import limits

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# `polls` is a symlink to the repository's poll definitions; CDK follows it
# when it builds the function bundle, so the deployed folder holds real files.
BUNDLED_DEFINITIONS_DIR = Path(__file__).parent / "polls"


def load_definitions(directory):
    """Return the poll definitions in `directory`, keyed by poll ID."""
    definitions = {}
    for path in sorted(Path(directory).glob("*.json")):
        definition = json.loads(path.read_text(encoding="utf-8"))
        definitions[definition["id"]] = definition
    return definitions


def _encode(number, length):
    """Encode a number as `length` Crockford base32 characters."""
    chars = []
    for _ in range(length):
        number, digit = divmod(number, 32)
        chars.append(_CROCKFORD[digit])
    return "".join(reversed(chars))


def _new_response_id(when):
    """Return a time-sortable ID: 48-bit millisecond time, 80 random bits."""
    milliseconds = int(when.timestamp() * 1000)
    return _encode(milliseconds, 10) + _encode(secrets.randbits(80), 16)


def _response(status, payload):
    """Build a Function URL response with a JSON body."""
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


class _Rejected(Exception):
    """A request that is turned away, with its status and reason."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _check_route(event):
    """Only POST requests to /submit are served."""
    http = event["requestContext"]["http"]
    if http["path"] != "/submit":
        raise _Rejected(404, "not_found")
    if http["method"] != "POST":
        raise _Rejected(405, "method_not_allowed")


def _parse_body(event):
    """Return the parsed request, or raise if it is not a well-formed one."""
    body = event.get("body") or ""
    if len(body.encode("utf-8")) > limits.MAX_BODY_BYTES:
        raise _Rejected(413, "payload_too_large")
    try:
        request = json.loads(body)
    except json.JSONDecodeError as error:
        raise _Rejected(400, "invalid_json") from error
    if not (
        isinstance(request, dict)
        and isinstance(request.get("pollId"), str)
        and isinstance(request.get("answers"), dict)
    ):
        raise _Rejected(400, "invalid_request")
    return request


def _check_single(question, value):
    """A single-choice answer is one of the question's option IDs."""
    if not isinstance(value, str):
        raise _Rejected(400, "invalid_answer")
    if value not in {option["id"] for option in question["options"]}:
        raise _Rejected(400, "unknown_option")


def _check_multi(question, value):
    """Multiple-choice answers are lists of the question's option IDs."""
    if not isinstance(value, list) or not all(
        isinstance(option_id, str) for option_id in value
    ):
        raise _Rejected(400, "invalid_answer")
    if not value:
        raise _Rejected(400, "missing_answer")
    option_ids = {option["id"] for option in question["options"]}
    for option_id in value:
        if option_id not in option_ids:
            raise _Rejected(400, "unknown_option")
    if len(set(value)) != len(value):
        raise _Rejected(400, "duplicate_option")


def _check_rating(question, value):
    """A rating is a whole number from the question's min to its max."""
    # bool is a subclass of int in Python, so exclude it explicitly
    if isinstance(value, bool) or not isinstance(value, int):
        raise _Rejected(400, "invalid_answer")
    if not question["min"] <= value <= question["max"]:
        raise _Rejected(400, "rating_out_of_range")


def _check_text(_question, value):
    """A free-text answer is a non-blank string within the length cap."""
    if not isinstance(value, str):
        raise _Rejected(400, "invalid_answer")
    if not value.strip():
        raise _Rejected(400, "missing_answer")
    if len(value) > limits.MAX_TEXT_CHARS:
        raise _Rejected(400, "answer_too_long")


_ANSWER_CHECKS = {
    "single": _check_single,
    "multi": _check_multi,
    "rating": _check_rating,
    "text": _check_text,
}


def _check_answers(definition, answers):
    """Raise unless the answers fit the poll's questions."""
    question_ids = {question["id"] for question in definition["questions"]}
    if set(answers) - question_ids:
        raise _Rejected(400, "unknown_question")
    for question in definition["questions"]:
        if question["id"] not in answers:
            raise _Rejected(400, "missing_answer")
        _ANSWER_CHECKS[question["type"]](question, answers[question["id"]])


def _validated(event, definitions):
    """Return (definition, answers) for a valid submission or raise."""
    _check_route(event)
    request = _parse_body(event)
    definition = definitions.get(request["pollId"])
    if definition is None:
        raise _Rejected(404, "unknown_poll")
    _check_answers(definition, request["answers"])
    return definition, request["answers"]


def handle(event, *, table, definitions, now, new_id=None):
    """Process one Function URL event and return the HTTP response."""
    new_id = new_id or _new_response_id
    try:
        definition, answers = _validated(event, definitions)
    except _Rejected as rejection:
        return _response(rejection.status, {"reason": rejection.reason})
    submitted = now()
    response_id = new_id(submitted)
    table.put_item(
        Item={
            "pk": f"POLL#{definition['id']}",
            "sk": f"RESPONSE#{response_id}",
            "answers": answers,
            "submittedAt": submitted.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pollVersion": definition["version"],
        }
    )
    return _response(201, {"responseId": response_id})


@functools.lru_cache(maxsize=1)
def _bundled_definitions():
    """Load the bundled poll definitions once per execution environment."""
    return load_definitions(BUNDLED_DEFINITIONS_DIR)


@functools.lru_cache(maxsize=1)
def _table():
    """Return the responses table named by the TABLE_NAME variable."""
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def handler(event, context):  # pylint: disable=unused-argument
    """Lambda entry point: wire the real table, definitions and clock."""
    return handle(
        event,
        table=_table(),
        definitions=_bundled_definitions(),
        now=lambda: datetime.now(timezone.utc),
    )
