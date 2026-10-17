Status: ready-for-agent
Type: AFK
Blocked by: 03

# 04. Multiple-choice and rating questions

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Extend validation and the page to multiple-choice (list of option IDs) and rating (integer within the question's bounds), using the fixed answer shapes from the spec.

## Acceptance criteria

- [x] Entry-point tests for each type: valid answers store in the fixed shape; unknown options, duplicate options, out-of-range or non-integer ratings are rejected with a reason.
- [ ] The page renders both types and shows a clear message for a missed or invalid answer before submitting.
- [ ] The poll definition checks (slice 07 once merged) and the example poll cover both types.
- [x] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 4, 5, 11, 26

## Comments

- 2026-10-17: claimed; same seams as slice 03 (handler entry point, page logic). Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; two items need the owner

Built test-first at the confirmed seams (handler entry point, page logic). Gate: pylint 10.00, 80 Python tests, 7 Node tests; no golden file changed (poll content only changes asset hashes, which are normalized).

**Handler** (45 tests, up from 18): answer checking is now per question type.
- Single choice: a string that is one of the options, else `invalid_answer` / `unknown_option`. (An old case, a list for a single-choice question, changed from `invalid_request` to `invalid_answer`, as agreed.)
- Multiple choice: must be a list of strings (a bare string such as `"xy"` is `invalid_answer`, not two options); empty is `missing_answer`; any unknown option is `unknown_option`; a repeat is `duplicate_option`.
- Rating: must be a JSON integer (floats, `3.0`, strings, null, lists, objects and `true`/`false` are `invalid_answer`; booleans are excluded explicitly because Python counts them as integers); outside the question's inclusive `min`..`max` is `rating_out_of_range`.
- Stored as sent: `{"q1": "a", "q2": ["x", "z"], "q3": 4}`.

**Page logic** (7 Node tests): new `missingQuestions(questions, answers)`: an empty multi selection and a missing rating count as unanswered, a rating of 0 counts as answered.

**Page** (DOM glue, not unit-tested): checkboxes for multiple choice, numbered radio buttons from `min` to `max` for ratings, answers read in the right shapes, and the tested function decides whether to show 'Please answer every question.'

**Example poll**: new `polls/poll2.json` (one question of each type, placeholder wording); `poll1` untouched so the gate-check script still works. Two tests keep it honest: every poll in the function bundle accepts a valid submission built from its own question types, and the bundle-contents test now compares against the real `polls/` folder, so adding a poll needs no test edit.

Not done:
- [ ] The page renders both types and shows a clear message for a missed answer (needs `make deploy-polls`, then a look at `https://polls.natenite.net/poll2` in a browser: tick a few boxes, rate, try submitting with a question left blank, then submit properly).
- [ ] The poll definition checks (slice 07) are not built yet; the example poll covering both types is done.
