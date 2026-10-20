Status: ready-for-agent
Type: AFK
Blocked by: 04

# 05. Timestamp-plus-random response IDs

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Replace the hand-rolled Crockford response-ID encoder with a UTC timestamp (microseconds) followed by a separator and 64 random bits as hex, for example `20261016T120000123456Z-9f2c1a7e44b0d3a1`. IDs still sort by submission time and read well in the results output; the ID generator stays injectable for tests. Nothing parses the ID: the results and email scripts match only the record-type prefixes. See [Grill: submit handler structure](../tickets/03-grill-handler-structure.md), decision 3. The pre-deploy check on stored data belongs to the deploy slice.

## Acceptance criteria

- [x] The encoder, its alphabet constant and the bit arithmetic are removed.
- [x] A test shows IDs sort in submission order, including two submissions within the same millisecond, and that two IDs for the same instant differ.
- [x] The results script and email script tests pass unchanged.
- [x] The PR states that old-format and new-format IDs sort wrongly against each other, pointing at the pre-deploy check in the deploy slice.
- [x] `make static` passes.

## Blocked by

- Blocked by [Trim the function's log line and consolidate its logging tests](04-trim-the-log-line.md)

## User stories addressed

Spec user stories: 18

## Comments

Done (uncommitted) in `lambda/submit/handler.py` and
`tests/unit/lambda_submit/test_handler.py`.

- **Handler:** removed `_CROCKFORD`, `_encode` and the bit arithmetic.
  `_new_response_id` is now
  `f"{utc:%Y%m%dT%H%M%S%f}Z-{secrets.token_hex(8)}"` on the time converted to
  UTC, for example `20261016T120000123456Z-9f2c1a7e44b0d3a1`. The time is
  converted with `astimezone(timezone.utc)` so a timezone-aware time that is not
  UTC gives the same ID as before the change would have (the old code used
  `timestamp()`, which is timezone-agnostic). `new_id` is still injectable.
- **Tests:** the sort test now uses microsecond offsets (three fall inside the
  first millisecond, the last is a minute later) and still needs six distinct
  keys; a new test shows two submissions at the same instant get different IDs;
  a new test spells out the expected shape by hand for the fixed clock
  (`20261016T120000000000Z-` then 16 hex digits) and checks a submission made
  with a UTC-4 clock gives the same prefix.
- `tests/unit/scripts` pass unchanged (225 passed across the handler and script
  tests before the full gate). Nothing parses the ID.
- `make static` and the read-only `make static-check` exit 0: pylint 10.00/10,
  280 Python tests (278 before, plus the two new ones) and 41 Node tests.
  Black reformatted one line during `make static`.
- **Deploy warning (for the deploy slice, not this one):** IDs in the old
  26-character Crockford format and the new format sort wrongly against each
  other, so before this ships the deployed table must hold no responses worth
  keeping, or be cleared. The slice "Deploy and verify the simplified stack"
  carries that pre-deploy check.
- Not touched: the owner guide still shows `"sk": "RESPONSE#01K..."` in its
  example output; the owner-guide slice corrects it.
