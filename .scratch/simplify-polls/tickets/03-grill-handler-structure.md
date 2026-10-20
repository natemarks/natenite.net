---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: submit handler structure

## Question

`lambda/submit/handler.py` (356 lines) holds route and body checks, per-type
answer checks, email and token handling, Crockford-base32 response IDs, the
two DynamoDB writes, and structured log shaping, with a `facts` dict threaded
through each step and a `_Services` namedtuple for testability.

What would make it easier to maintain: leave the shape and tidy, split into
focused modules, replace hand-written pieces (for example the ID generator or
log shaping) with simpler ones, or collapse the `facts`/services plumbing?
Weigh against the 1,179-line handler test file that currently pins the
behaviour.

## Resolution

Decided with the human, one branch at a time. Finding: the handler is already
a set of small single-purpose functions (request checks, storage, log shaping,
wiring); the accidental complexity was the log line's fields, the `facts`
side channel they fed, and the hand-rolled response-ID encoder, not the file
structure.

1. **Trim the log line to fields something reads.** After
   [Grill: observability layers](01-grill-observability-layers.md) only two
   saved queries read the log. Drop `cloudfrontRequestId` (existed to
   correlate with the removed access logs; nobody sends the header), `hasEmail`
   and `hasBrowserToken` (the table already answers both for accepted
   responses; rejections and storage failures log their own reason),
   `at` (Lambda's `@timestamp` and the stored `submittedAt` cover it) and
   `event` (platform lines are not JSON, so queries on `outcome` and `level`
   already skip them). **Keep `bodyBytes`:** ticket 02 dropped the body-budget
   check on the grounds that an oversized poll shows up as a 413 at launch,
   and the size is what separates a poll that outgrew the 6 KB limit from
   abuse; it is computed from the event inside `_log`, so it needs no `facts`
   plumbing. Result: `level`, `outcome`, `status`, `reason`, `pollId`,
   `responseId`, `bodyBytes`, `requestId`, `errorType`, `errorCode`. The
   invariant that no line holds email or answer text stays, with its test.
   `facts` shrinks to `pollId`, `responseId`, `requestId` and `failure`, and
   `_validated` stops recording the two flags.
2. **Leave the wiring.** Keep the `facts` dict, `_Services` and the `handle`
   / `handler` split. They are small after the trim and are the seam that lets
   the 49 handler tests run without AWS or a real clock. Rejected: a result
   dataclass with `pollId` carried on `_Rejected` (every raise site would need
   to know what had been learned so far, and many tests would change).
3. **Replace the Crockford response ID with a timestamp-plus-random ID.**
   For example `f"{when:%Y%m%dT%H%M%S%f}Z-{secrets.token_hex(8)}"`. It is
   equally sortable (spec user story 35), readable in `dump_poll` output, and
   removes `_CROCKFORD`, `_encode` and the bit arithmetic (about 14 lines
   become one). `test_response_ids_sort_in_submission_order` stays as the
   guard and `new_id` stays injectable. Nothing parses the ID: `dump_poll`
   and `manage_emails` match only the `RESPONSE#` and `EMAIL#` prefixes.
   **Pre-deploy step for the build:** IDs in the old and new formats sort
   wrongly against each other, so before this ships confirm the deployed table
   holds no responses worth keeping, or clear it. The human was asked and did
   not say either way; the launch-verification slice has not run, so none is
   expected.
4. **Keep `handler.py` as one file** (about 320 lines after these changes).
   A validation/storage split would mostly relocate code and would want
   `test_handler.py` (1,179 lines) split to match, while the tests today drive
   one `handle()` call and pin behaviour, not structure. Revisit if a new
   question type or field pushes it well past 400 lines.

Consequences for other tickets:

- [Grill: test suite size and overlap](05-grill-test-suite-size.md): tests that
  pin the dropped log fields change (`test_an_accepted_submission_logs_one_structured_line`,
  `test_request_ids_and_yes_no_flags_pass_through` and the assertions on
  `hasEmail`, `hasBrowserToken`, `cloudfrontRequestId`, `at`, `event` in the
  log tests); the file is not split.
- [Grill: owner scripts and docs](06-grill-owner-scripts-and-docs.md):
  `POLLS.md` lists the log fields (`hasEmail`, `hasBrowserToken`,
  `cloudfrontRequestId`) and must follow the trimmed set.
- [Grill: stack layout and WAF rule ownership](04-grill-stack-layout.md): no
  effect beyond the saved queries already decided in ticket 01.
