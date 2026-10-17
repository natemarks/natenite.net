"""Checks for poll definition files.

Purpose:
- Report what is wrong with a poll definition as a list of problems, so a bad
  poll file can fail the unit tests before it is deployed.
"""

import json
import re
from datetime import datetime, timezone

import limits

# The page fetches /definitions/<id>.json, so the ID doubles as a file name
# and a URL path segment.
_POLL_ID = re.compile(r"[a-z0-9-]+")
# Question IDs become form field names and answer keys.
_QUESTION_ID = re.compile(r"[a-z][a-z0-9_]*")
_QUESTION_TYPES = ("single", "multi", "rating", "text")
# The page draws one button per rating value.
_MAX_RATING_STEPS = 10


_CLOSES_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_closes_at(text):
    """Parse a UTC closing time such as 2026-12-31T23:59:59Z.

    Raises ValueError for anything else, including other time zones.
    """
    if not isinstance(text, str):
        raise ValueError("closesAt must be a string")
    parsed = datetime.strptime(text, _CLOSES_AT_FORMAT)
    return parsed.replace(tzinfo=timezone.utc)


def _blank(value):
    """True unless `value` is a string with something other than spaces."""
    return not isinstance(value, str) or not value.strip()


def _check_identity(definition, file_stem):
    """Rules for the ID, the file name, the version and the title."""
    problems = []
    poll_id = definition.get("id")
    if not isinstance(poll_id, str) or not _POLL_ID.fullmatch(poll_id):
        problems.append("id must be lower-case letters, digits and hyphens")
    elif poll_id != file_stem:
        problems.append(
            f"file name '{file_stem}.json' must match the id '{poll_id}'"
        )
    version = definition.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
    ):
        problems.append("version must be a whole number of at least 1")
    if _blank(definition.get("title")):
        problems.append("title must be a non-empty string")
    if "closesAt" in definition:
        try:
            parse_closes_at(definition["closesAt"])
        except ValueError:
            problems.append(
                "closesAt must look like 2026-12-31T23:59:59Z (UTC)"
            )
    return problems


def _check_options(label, question):
    """Rules for the options of a single- or multiple-choice question."""
    options = question.get("options")
    if not isinstance(options, list) or len(options) < 2:
        return [f"{label}: options must be a list of at least two options"]
    problems = []
    seen = set()
    for option in options:
        if not isinstance(option, dict):
            problems.append(f"{label}: each option must be an object")
            continue
        option_id = option.get("id")
        if not isinstance(option_id, str) or not option_id:
            problems.append(f"{label}: option id must be a non-empty string")
        elif option_id in seen:
            problems.append(f"{label}: duplicate option id '{option_id}'")
        else:
            seen.add(option_id)
        if _blank(option.get("label")):
            problems.append(
                f"{label}: option label must be a non-empty string"
            )
    return problems


def _is_whole(value):
    """True for a JSON integer (a boolean is not one)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_rating(label, question):
    """Rules for a rating question's bounds."""
    low, high = question.get("min"), question.get("max")
    if not (_is_whole(low) and _is_whole(high)):
        return [f"{label}: rating min and max must be whole numbers"]
    if not low < high <= low + _MAX_RATING_STEPS:
        return [
            f"{label}: rating min must be below max, at most "
            f"{_MAX_RATING_STEPS} steps apart"
        ]
    return []


def _check_questions(definition):
    """Rules for the list of questions and each question's basics."""
    questions = definition.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions must be a non-empty list"]
    problems = []
    seen = set()
    for number, question in enumerate(questions, start=1):
        label = f"question {number}"
        if not isinstance(question, dict):
            problems.append(f"{label} must be an object")
            continue
        question_id = question.get("id")
        if not isinstance(question_id, str) or not _QUESTION_ID.fullmatch(
            question_id
        ):
            problems.append(
                f"{label}: question id must start with a lower-case letter "
                "and use only lower-case letters, digits and underscores"
            )
        elif question_id in seen:
            problems.append(f"{label}: duplicate question id '{question_id}'")
        else:
            seen.add(question_id)
        if question.get("type") not in _QUESTION_TYPES:
            problems.append(
                f"{label}: type must be one of {', '.join(_QUESTION_TYPES)}"
            )
        if _blank(question.get("prompt")):
            problems.append(f"{label}: prompt must be a non-empty string")
        if question.get("type") in ("single", "multi"):
            problems += _check_options(label, question)
        elif question.get("type") == "rating":
            problems += _check_rating(label, question)
    return problems


def worst_case_body_bytes(definition):
    """Size in bytes of the largest submission a valid poll can receive.

    Longest option for single choice, every option for multiple choice, the
    widest value for ratings, and a full-length answer of 4-byte characters
    for free text. Expects a structurally valid definition.
    """
    answers = {}
    for question in definition["questions"]:
        kind = question["type"]
        if kind == "single":
            answers[question["id"]] = max(
                (option["id"] for option in question["options"]), key=len
            )
        elif kind == "multi":
            answers[question["id"]] = [
                option["id"] for option in question["options"]
            ]
        elif kind == "rating":
            answers[question["id"]] = max(
                (question["min"], question["max"]),
                key=lambda number: (len(str(number)), number),
            )
        else:
            answers[question["id"]] = "\U0001f600" * limits.MAX_TEXT_CHARS
    body = json.dumps(
        {"pollId": definition["id"], "answers": answers},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return len(body.encode("utf-8"))


def _check_body_budget(definition):
    """The largest submission, plus reserved room, must fit the body limit."""
    needed = worst_case_body_bytes(definition) + limits.RESERVED_BODY_BYTES
    if needed > limits.MAX_BODY_BYTES:
        return [
            f"body: the largest possible submission needs {needed} bytes "
            f"including {limits.RESERVED_BODY_BYTES} reserved, over the "
            f"{limits.MAX_BODY_BYTES} byte limit"
        ]
    return []


def validate(definition, file_stem):
    """Return the problems found in a poll definition (empty when fine)."""
    if not isinstance(definition, dict):
        return ["a poll definition must be a JSON object"]
    problems = _check_identity(definition, file_stem) + _check_questions(
        definition
    )
    if not problems:
        problems += _check_body_budget(definition)
    return problems
