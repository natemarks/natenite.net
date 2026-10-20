Status: ready-for-agent
Type: AFK
Blocked by: none

# 02. Drop the request-size budget check from poll files

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Remove the worst-case request-size computation, its check and the reserved-bytes constant from the poll checks, together with the tests that cover them. The shared limits keep the body limit, the free-text limit and the email limit. The structural checks on poll files (id and file name, version, title, closing time, questions, options, rating bounds) and the free-text contract test stay. A poll too large to submit now shows up as a 413 on the first test submission. See [Grill: poll definition rules and shared limits](../tickets/02-grill-poll-definition-rules.md), decision 1.

## Acceptance criteria

- [x] The worst-case size function, its check and the reserved-bytes constant no longer exist, and nothing references them.
- [x] The tests that covered them are removed (four tests and the helper they shared; the issue first said five); every structural check still has its test.
- [x] The function still answers 413 `payload_too_large` for a body over the limit (existing test).
- [x] The free-text contract test passes.
- [x] `make static` passes.

## Blocked by

None - can start immediately

## User stories addressed

Spec user stories: 16, 17, 28

## Comments

Done (uncommitted) in `lambda/submit/definitions.py`, `lambda/submit/limits.py`
and `tests/unit/lambda_submit/test_definitions.py`.

- Removed `worst_case_body_bytes`, `_check_body_budget`, `RESERVED_BODY_BYTES`,
  four tests (worst-case size, two and three free-text questions, 400 options)
  and the `with_text_questions` helper only they used. `definitions.py` no
  longer imports `json` or `limits`, so the `limits.py` docstring now says the
  limits are the submit function's, not "shared with the poll definition
  checks". `limits.py` holds `MAX_BODY_BYTES`, `MAX_TEXT_CHARS`,
  `MAX_EMAIL_CHARS`.
- A poll the old check rejected (three free-text questions plus 400 options)
  now passes the lint; the function's own 413 `payload_too_large` test still
  covers an oversize body, and the free-text contract test still passes.
- Side effect: `validate` now always returns a plain list, so pylint can infer
  it and flagged four existing `== []` assertions (C1803). Those four became
  `assert not ...`; meaning unchanged.
- `make static` exits 0: black unchanged, pylint 10.00/10, 284 Python tests
  (288 before, minus 4) and 41 Node tests pass.
- Not done here, by design: `POLLS.md` still says a poll holds at most two
  free-text questions and that the tests catch a poll too big to submit. That
  is fixed in the owner-guide slice.
