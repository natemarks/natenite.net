"""Behavior tests for the poll definition checks.

Purpose:
- Say what is wrong with a poll definition, as a list of problems, so a bad
  poll file fails the unit-test gate before it can be deployed.
- Run the checks over every real poll file in the repository.
"""

# pylint: disable=duplicate-code
import copy
import json

import pytest

import definitions
from config.helper import PROJECT_ROOT

VALID = {
    "id": "demo",
    "title": "Demo poll",
    "version": 1,
    "closesAt": "2026-12-31T23:59:59Z",
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
            "options": [{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}],
        },
        {"id": "q3", "type": "rating", "prompt": "Rate", "min": 1, "max": 5},
        {"id": "q4", "type": "text", "prompt": "Anything else?"},
    ],
}


def problems_for(change, name="demo"):
    """Problems found in VALID after `change` edits a copy of it."""
    definition = copy.deepcopy(VALID)
    change(definition)
    return definitions.validate(definition, name)


@pytest.mark.unit
def test_a_well_formed_definition_has_no_problems():
    """Every question type, a closing time, nothing wrong."""
    assert definitions.validate(copy.deepcopy(VALID), "demo") == []


def assert_problem(change, fragment, name="demo"):
    """The change makes the checks report a problem mentioning `fragment`."""
    problems = problems_for(change, name)
    assert any(fragment in problem for problem in problems), problems


def drop(key):
    """A change that removes a top-level key."""
    return lambda d: d.pop(key)


def put(key, value):
    """A change that sets a top-level key."""
    return lambda d: d.update({key: value})


@pytest.mark.unit
@pytest.mark.parametrize(
    "change, fragment, name",
    [
        pytest.param(drop("id"), "id", "demo", id="id-missing"),
        pytest.param(put("id", "Demo"), "id", "Demo", id="id-upper-case"),
        pytest.param(put("id", "a b"), "id", "a b", id="id-with-a-space"),
        pytest.param(put("id", 5), "id", "demo", id="id-not-a-string"),
        pytest.param(put("id", "other"), "file name", "demo", id="id-vs-file"),
        pytest.param(drop("version"), "version", "demo", id="version-missing"),
        pytest.param(put("version", "1"), "version", "demo", id="version-str"),
        pytest.param(put("version", 0), "version", "demo", id="version-zero"),
        pytest.param(
            put("version", True), "version", "demo", id="version-true"
        ),
        pytest.param(
            put("version", 1.5), "version", "demo", id="version-float"
        ),
        pytest.param(drop("title"), "title", "demo", id="title-missing"),
        pytest.param(put("title", "   "), "title", "demo", id="title-blank"),
        pytest.param(
            put("title", 5), "title", "demo", id="title-not-a-string"
        ),
    ],
)
def test_identity_version_and_title_are_checked(change, fragment, name):
    """Poll ID, file name, version and title each have rules."""
    assert_problem(change, fragment, name)


@pytest.mark.unit
def test_a_definition_that_is_not_an_object_is_reported():
    """A JSON file holding a list or a number is not a poll."""
    assert definitions.validate([], "demo")
    assert definitions.validate(5, "demo")


@pytest.mark.unit
@pytest.mark.parametrize(
    "closes_at",
    [
        pytest.param("2026-12-31", id="date-only"),
        pytest.param("2026-12-31T23:59:59", id="no-timezone"),
        pytest.param("2026-12-31T23:59:59+00:00", id="offset-instead-of-z"),
        pytest.param("2026-12-31T23:59:59-05:00", id="other-timezone"),
        pytest.param("2026-13-01T00:00:00Z", id="no-such-month"),
        pytest.param("2026-02-30T00:00:00Z", id="no-such-day"),
        pytest.param("", id="empty"),
        pytest.param(20261231, id="number"),
    ],
)
def test_a_closing_time_must_be_a_utc_timestamp(closes_at):
    """Only `YYYY-MM-DDTHH:MM:SSZ` is accepted, so it is never ambiguous."""
    assert_problem(put("closesAt", closes_at), "closesAt")


@pytest.mark.unit
def test_a_closing_time_is_optional():
    """A poll without `closesAt` is fine."""
    assert problems_for(drop("closesAt")) == []


def question(index):
    """A change that edits the question at `index` through a callback."""

    def apply(edit):
        return lambda d: edit(d["questions"][index])

    return apply


@pytest.mark.unit
@pytest.mark.parametrize(
    "change, fragment",
    [
        pytest.param(drop("questions"), "questions", id="questions-missing"),
        pytest.param(put("questions", []), "questions", id="questions-empty"),
        pytest.param(put("questions", "q1"), "questions", id="questions-str"),
        pytest.param(put("questions", ["q1"]), "question", id="question-str"),
        pytest.param(
            lambda d: d["questions"][1].update(id="q1"),
            "duplicate question id",
            id="duplicate-question-id",
        ),
        pytest.param(
            lambda d: d["questions"][0].update(id="Q1"),
            "question id",
            id="question-id-upper-case",
        ),
        pytest.param(
            lambda d: d["questions"][0].update(id="1q"),
            "question id",
            id="question-id-starts-with-a-digit",
        ),
        pytest.param(
            lambda d: d["questions"][0].update(id="a-b"),
            "question id",
            id="question-id-with-a-hyphen",
        ),
        pytest.param(
            lambda d: d["questions"][0].pop("id"),
            "question id",
            id="question-id-missing",
        ),
        pytest.param(
            lambda d: d["questions"][0].update(type="essay"),
            "type",
            id="unknown-type",
        ),
        pytest.param(
            lambda d: d["questions"][3].pop("type"),
            "type",
            id="type-missing",
        ),
        pytest.param(
            lambda d: d["questions"][2].update(prompt="  "),
            "prompt",
            id="prompt-blank",
        ),
        pytest.param(
            lambda d: d["questions"][2].pop("prompt"),
            "prompt",
            id="prompt-missing",
        ),
    ],
)
def test_question_structure_is_checked(change, fragment):
    """Questions need IDs, a known type and a prompt."""
    assert_problem(change, fragment)


@pytest.mark.unit
@pytest.mark.parametrize("index", [0, 1], ids=["single", "multi"])
@pytest.mark.parametrize(
    "edit, fragment",
    [
        pytest.param(lambda q: q.pop("options"), "options", id="missing"),
        pytest.param(lambda q: q.update(options=[]), "options", id="empty"),
        pytest.param(
            lambda q: q.update(options=[{"id": "a", "label": "A"}]),
            "options",
            id="only-one",
        ),
        pytest.param(
            lambda q: q.update(options="a,b"), "options", id="a-string"
        ),
        pytest.param(
            lambda q: q.update(options=["a", "b"]), "option", id="not-objects"
        ),
        pytest.param(
            lambda q: q.update(
                options=[{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]
            ),
            "duplicate option id",
            id="duplicate-ids",
        ),
        pytest.param(
            lambda q: q.update(
                options=[{"id": "", "label": "A"}, {"id": "b", "label": "B"}]
            ),
            "option id",
            id="empty-id",
        ),
        pytest.param(
            lambda q: q.update(
                options=[{"id": 1, "label": "A"}, {"id": "b", "label": "B"}]
            ),
            "option id",
            id="numeric-id",
        ),
        pytest.param(
            lambda q: q.update(
                options=[{"id": "a", "label": " "}, {"id": "b", "label": "B"}]
            ),
            "label",
            id="blank-label",
        ),
        pytest.param(
            lambda q: q.update(
                options=[{"id": "a"}, {"id": "b", "label": "B"}]
            ),
            "label",
            id="missing-label",
        ),
    ],
)
def test_choice_options_are_checked(index, edit, fragment):
    """Single and multiple choice need two or more distinct, labelled options."""
    assert_problem(question(index)(edit), fragment)


@pytest.mark.unit
@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda q: q.pop("min"), id="min-missing"),
        pytest.param(lambda q: q.pop("max"), id="max-missing"),
        pytest.param(lambda q: q.update(min="1"), id="min-str"),
        pytest.param(lambda q: q.update(max=5.5), id="max-float"),
        pytest.param(lambda q: q.update(min=True), id="min-true"),
        pytest.param(lambda q: q.update(min=5, max=5), id="min-equals-max"),
        pytest.param(lambda q: q.update(min=6, max=2), id="min-above-max"),
        pytest.param(lambda q: q.update(min=0, max=11), id="eleven-steps"),
        pytest.param(
            lambda q: q.update(min=-3, max=8), id="eleven-steps-negative"
        ),
    ],
)
def test_rating_bounds_are_checked(edit):
    """A rating needs whole-number bounds, min below max, at most 10 steps."""
    assert_problem(question(2)(edit), "rating")


@pytest.mark.unit
@pytest.mark.parametrize(
    "bounds",
    [(1, 2), (0, 10), (1, 5), (-5, 5)],
    ids=["two-points", "zero-to-ten", "one-to-five", "negative-to-positive"],
)
def test_reasonable_rating_bounds_are_accepted(bounds):
    """Scales up to 10 steps wide are fine."""

    def change(d):
        d["questions"][2].update(min=bounds[0], max=bounds[1])

    assert problems_for(change) == []


@pytest.mark.unit
def test_worst_case_body_is_the_longest_submission_the_poll_allows():
    """Longest option, every multi option, widest rating, 500 emoji of text."""
    # Built by hand, not with json.dumps, so it is independent of the code.
    expected = (
        '{"pollId":"demo","answers":{"q1":"a","q2":["x","y"],"q3":5,'
        '"q4":"' + "\U0001f600" * 500 + '"}}'
    )

    assert definitions.worst_case_body_bytes(VALID) == len(
        expected.encode("utf-8")
    )


def with_text_questions(count):
    """A change that makes the poll have `count` free-text questions."""

    def change(d):
        d["questions"] = [
            {"id": f"t{n}", "type": "text", "prompt": "Tell us more"}
            for n in range(count)
        ]

    return change


@pytest.mark.unit
def test_two_long_free_text_questions_fit_the_size_budget():
    """Two 500-character answers plus the reserved room are within 6 KB."""
    assert problems_for(with_text_questions(2)) == []


@pytest.mark.unit
def test_three_long_free_text_questions_exceed_the_size_budget():
    """Three 500-character answers could not be submitted in the worst case."""
    assert_problem(with_text_questions(3), "body")


@pytest.mark.unit
def test_a_choice_question_with_very_many_options_exceeds_the_budget():
    """Selecting every option of a huge multiple-choice question is too big."""

    def change(d):
        d["questions"][1]["options"] = [
            {"id": f"option-number-{n:04d}", "label": "L"} for n in range(400)
        ]

    assert_problem(change, "body")


POLL_FILES = sorted((PROJECT_ROOT / "polls").glob("*.json"))


@pytest.mark.unit
def test_there_are_poll_definitions_to_check():
    """Guard against the check below passing because it found no files."""
    assert POLL_FILES


@pytest.mark.unit
@pytest.mark.parametrize("path", POLL_FILES, ids=[p.name for p in POLL_FILES])
def test_every_poll_definition_in_the_repository_is_valid(path):
    """A bad poll file fails the unit tests before it can be deployed."""
    definition = json.loads(path.read_text(encoding="utf-8"))

    problems = definitions.validate(definition, path.stem)

    assert problems == [], f"{path.name} has problems:\n- " + "\n- ".join(
        problems
    )
