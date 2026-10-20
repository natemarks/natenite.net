Status: ready-for-agent
Type: AFK
Blocked by: none

# 04. Trim the function's log line and consolidate its logging tests

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Trim the function's one-line-per-request log to the fields something reads: level, outcome, status, reason, poll ID, response ID, body size, request ID and, for failures, the error type and error code. Remove the CloudFront request ID, the has-email and has-token flags, the event timestamp and the constant event name. Shrink the internal facts record to poll ID, response ID, request ID and the failure, and stop recording the two flags during validation. The rule that no line holds email, answer text, token or token hash stays. Consolidate the logging tests so each behaviour is pinned once: fold the request ID into the accepted-line test; cut the rejection-logging table to a bad answer on a real poll, a hostile poll ID (no log-line injection) and a closed poll; delete the email-only privacy test and the request-ID/flags passthrough test; keep the one comprehensive no-personal-data test, the oversize body logged by size, the lost email, and the unexpected failure logged by error kind only. See [Grill: submit handler structure](../tickets/03-grill-handler-structure.md), decision 1, and [Grill: test suite size and overlap](../tickets/05-grill-test-suite-size.md), decision 3.

## Acceptance criteria

- [x] Every log line has exactly the ten fields above (failure fields only on failures); the removed fields are gone from the code and the tests.
- [x] The accepted-line test asserts the new shape including the request ID.
- [x] The rejection-logging test covers the three cases above; the email-only privacy test and the passthrough test are deleted.
- [x] The comprehensive test still proves no email, answer text, token or token hash appears in any line across accepted, rejected and failed requests.
- [x] Handler behaviour and responses are unchanged.
- [x] `make static` passes.

## Blocked by

None - can start immediately

## User stories addressed

Spec user stories: 11, 12, 29, 30

## Comments

Done (uncommitted) in `lambda/submit/handler.py` and
`tests/unit/lambda_submit/test_handler.py`; this slice changes those two
files only.

- **Handler:** the log line is now level, outcome, status, poll ID, response
  ID, body size and request ID, plus reason (status 400 and up) and error type
  and code (failures). Removed `cloudfrontRequestId`, `hasEmail`,
  `hasBrowserToken`, `at` and `event`. `facts` has four keys (`pollId`,
  `responseId`, `requestId`, `failure`) and `_validated` no longer records the
  flags. Responses and behaviour are unchanged.
- **Tests:** the accepted-line test asserts the new shape with a request ID
  (the `submit` helper gained an optional `request_id`); the rejection-logging
  table is three cases (bad answer on a real poll, hostile poll ID, closed
  poll); the lost-email test no longer asserts `hasEmail`; the passthrough
  test and the email-only privacy test are deleted.
- **Correction to the plan:** the email-only privacy test was not strictly a
  subset of the comprehensive test: it also checked response bodies, stderr and
  the logging module's records, and it used a too-long email. Rather than lose
  that, the comprehensive test now also collects every response body, stderr
  and `caplog`, and gained a too-long-email request.
- **Mutation check:** with a deliberate leak of the raw body into the log line,
  and separately with `invalid_email` echoing the address in the response, the
  comprehensive test failed both times; the handler was restored byte for byte
  and the test passes again.
- `make static` and the read-only `make static-check` both exit 0: pylint
  10.00/10, 278 Python tests (284 before, minus 6: two deleted tests and four
  rejection cases) and 41 Node tests. Black reformatted one line in the test
  file during `make static`.
- Not touched, per the plan: the log group, saved queries, the owner guide's
  list of log fields (the owner-guide slice) and the response ID (next slice).
