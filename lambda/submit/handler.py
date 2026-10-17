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
import hashlib
import json
import os
import re
import secrets
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

import limits
from definitions import parse_closes_at

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# `polls` is a symlink to the repository's poll definitions; CDK follows it
# when it builds the function bundle, so the deployed folder holds real files.
BUNDLED_DEFINITIONS_DIR = Path(__file__).parent / "polls"

# Deliberately not a full RFC check, which would reject real addresses and
# still not prove the mailbox exists: one @, text on both sides, and a dot
# inside the domain (no empty parts), with no whitespace anywhere.
# The page makes the browser token from 128 random bits, as hex.
_TOKEN_SHAPE = re.compile(r"[0-9a-f]{32}")

_EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+")


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


def _check_open(definition, submitted):
    """A poll with a closing time stops taking responses at that instant."""
    closes_at = definition.get("closesAt")
    if closes_at is None:
        return
    if submitted >= parse_closes_at(closes_at):
        raise _Rejected(410, "poll_closed")


def _email_from(request):
    """The trimmed, valid email address, or None when none was given."""
    if "email" not in request:
        return None
    email = request["email"]
    if not isinstance(email, str):
        raise _Rejected(400, "invalid_email")
    email = email.strip()
    if not email:
        return None
    if len(email) > limits.MAX_EMAIL_CHARS:
        raise _Rejected(400, "email_too_long")
    if not _EMAIL_SHAPE.fullmatch(email):
        raise _Rejected(400, "invalid_email")
    return email


def _token_hash_from(request):
    """The SHA-256 (hex) of the browser token, or None when none was sent."""
    if "browserToken" not in request:
        return None
    token = request["browserToken"]
    if not isinstance(token, str) or not _TOKEN_SHAPE.fullmatch(token):
        raise _Rejected(400, "invalid_token")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validated(event, definitions, submitted, facts):
    """Return the parts of a valid submission, or raise.

    `facts` collects what is safe to log about the request as it is learned.
    """
    _check_route(event)
    request = _parse_body(event)
    definition = definitions.get(request["pollId"])
    if definition is None:
        raise _Rejected(404, "unknown_poll")
    # Only the ID of a real poll is ever recorded, never the requested text.
    facts["pollId"] = definition["id"]
    _check_open(definition, submitted)
    _check_answers(definition, request["answers"])
    token_hash = _token_hash_from(request)
    email = _email_from(request)
    facts["hasBrowserToken"] = token_hash is not None
    facts["hasEmail"] = email is not None
    return definition, request["answers"], email, token_hash


def _log(event, response, facts):
    """Print one JSON line describing the outcome: never any content."""
    headers = event.get("headers") or {}
    status = response["statusCode"]
    if status < 400:
        level, outcome = "INFO", "accepted"
    elif status < 500:
        level, outcome = "WARN", "rejected"
    else:
        level, outcome = "ERROR", "error"
    line = {
        "level": level,
        "event": "submission",
        "outcome": outcome,
        "status": status,
        "pollId": facts["pollId"],
        "responseId": facts["responseId"],
        "hasEmail": facts["hasEmail"],
        "hasBrowserToken": facts["hasBrowserToken"],
        "bodyBytes": len((event.get("body") or "").encode("utf-8")),
        "at": facts["at"],
        "requestId": facts["requestId"],
        "cloudfrontRequestId": headers.get("x-amz-cf-id"),
    }
    if status >= 400:
        line["reason"] = json.loads(response["body"]).get("reason")
    failure = facts["failure"]
    if failure is not None:
        # The kind of error only: its message can carry request details.
        line["errorType"] = type(failure).__name__
        if isinstance(failure, ClientError):
            line["errorCode"] = failure.response.get("Error", {}).get("Code")
    print(json.dumps(line))


# The collaborators `handle` is given: where responses are stored, the poll
# definitions, and how response IDs are made.
_Services = namedtuple("_Services", ["table", "definitions", "new_id"])


def _process(event, services, submitted, facts):
    """Validate and store one submission; return the HTTP response."""
    table = services.table
    try:
        definition, answers, email, token_hash = _validated(
            event, services.definitions, submitted, facts
        )
    except _Rejected as rejection:
        return _response(rejection.status, {"reason": rejection.reason})
    response_id = services.new_id(submitted)
    item = {
        "pk": f"POLL#{definition['id']}",
        "sk": f"RESPONSE#{response_id}",
        "answers": answers,
        "submittedAt": submitted.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pollVersion": definition["version"],
    }
    if token_hash:
        item["browserTokenHash"] = token_hash
    table.put_item(Item=item)
    facts["responseId"] = response_id
    if email:
        # The answers are already stored. If the email cannot be, say so
        # (the visitor may retry) without losing them or echoing the address.
        try:
            table.put_item(
                Item={
                    "pk": f"POLL#{definition['id']}",
                    "sk": f"EMAIL#{response_id}",
                    "email": email,
                    "submittedAt": submitted.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
        except ClientError:
            return _response(500, {"reason": "email_not_stored"})
    return _response(201, {"responseId": response_id})


def handle(  # pylint: disable=too-many-arguments
    event, *, table, definitions, now, new_id=None, request_id=None
):
    """Process one Function URL event and return the HTTP response."""
    submitted = now()
    facts = {
        "pollId": None,
        "responseId": None,
        "hasEmail": False,
        "hasBrowserToken": False,
        "at": submitted.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requestId": request_id,
        "failure": None,
    }
    services = _Services(table, definitions, new_id or _new_response_id)
    try:
        response = _process(event, services, submitted, facts)
    except Exception as error:  # pylint: disable=broad-exception-caught
        # Whatever went wrong, the visitor gets a clean 500 the page can
        # retry, and the log gets the kind of error.
        facts["failure"] = error
        response = _response(500, {"reason": "internal_error"})
    _log(event, response, facts)
    return response


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
        request_id=getattr(context, "aws_request_id", None),
    )
