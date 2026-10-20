Status: ready-for-agent
Type: AFK
Blocked by: none

# 01. Poll-file tests no longer break when a second poll is added

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Following the owner guide's "add a poll" steps must not fail the unit tests. Delete the test that pins the launch poll's title, option labels, closing time and the exact set of poll files (it fails as soon as a second poll file exists and goes stale when the poll closes). Merge the two near-duplicate "every bundled poll accepts a valid submission" tests into the parametrized one and delete the loop version and its duplicate answer-building helper. Keep the lint that validates every real poll file. See [Grill: test suite size and overlap](../tickets/05-grill-test-suite-size.md), decision 1.

## Acceptance criteria

- [x] The launch-poll content test is gone.
- [x] Adding a second valid poll file to `polls/` leaves `make unit-test` passing (shown in the PR, then removed); a deliberately invalid poll file still fails the lint.
- [x] One parametrized test per real poll file checks that a valid submission is accepted; the loop version and the duplicate helper are removed.
- [x] `make static` passes.

## Blocked by

None - can start immediately

## User stories addressed

Spec user stories: 15, 33, 34

## Comments

Done in `tests/unit/lambda_submit/test_handler.py` (uncommitted).

- Deleted `test_the_launch_poll_offers_the_four_november_dates_until_the_15th`.
- Deleted `test_every_bundled_definition_accepts_a_valid_submission` and its
  helper `a_valid_answer`. The one assertion the loop version had that the
  parametrized test lacked (the stored `pollVersion` equals the definition's)
  was added to `test_every_bundled_poll_accepts_a_valid_submission`.
- The lint test over every poll file is untouched.

Evidence (all run in this checkout, throwaway poll files removed afterwards):

- With the original tests, adding a second valid poll file failed
  `test_the_launch_poll_offers_the_four_november_dates_until_the_15th`
  (1 failed, 205 passed in `tests/unit/lambda_submit`).
- With the edit, a second valid poll file passes (290 passed across
  `tests/`, two more than the 288 baseline: its lint test and its
  submission test).
- With the edit, an invalid poll file (empty title, version 0, no questions)
  fails exactly one test, the lint, which names the file.
- `make static` exits 0: shellcheck clean, black unchanged, pylint 10.00/10,
  288 Python tests and 41 Node tests pass.
