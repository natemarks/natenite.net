---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: poll definition rules and shared limits

## Question

A poll's rules are enforced or restated in three runtimes: `definitions.py`
(deploy-time checks, run from tests), `handler.py` (per-question answer checks
at submit time), and `site/polls/lib.js` (page checks), with limits mirrored
between `limits.py` and `lib.js` by a regex contract test. The Lambda package
also imports the validator and limits, and the bundled `polls/` symlink carries
the definitions into the function.

What is the simplest arrangement that keeps one source of truth for the poll
rules and limits? Options include: keep as is, generate the JS constants from
the Python limits (or the reverse), move to a JSON schema shared by both
sides, or trim which layer checks what. Decide also whether the symlink bundle
stays.

## Resolution

Decided with the human, one branch at a time. Fact corrected while grilling:
`definitions.validate` is not a deploy-time check. It is called only from
`tests/unit/lambda_submit/test_definitions.py`, where one test runs it over
every file in `polls/` as part of `make static`; the Lambda imports only
`parse_closes_at` and `limits` from that package. The rules that look
duplicated across runtimes are mostly not: the handler's answer checks are the
authority and `lib.js` `missingQuestions` only drives page feedback; `isClosed`
only chooses what the page shows. The one true mirror is the free-text limit.

1. **Keep the poll-file lint, drop the body-budget check.** Keep the
   structural checks (ids, file name, version, title, `closesAt`, questions,
   options, rating bounds). Remove `worst_case_body_bytes`,
   `_check_body_budget` and `limits.RESERVED_BODY_BYTES`, and the five tests
   that cover them (`test_worst_case_body_is_the_longest_submission_the_poll_allows`
   and the four size-budget tests, about 60 lines in `test_definitions.py`).
   The closed
   `.scratch/wayfinder/poll-app/issues/07-closing-time-and-poll-checks.md`
   describes the budget check and is left as history. About 45 lines leave
   `definitions.py`. A poll too large
   to submit surfaces as a 413 on the first test submission in launch
   verification. Rejected: keeping it as is (the most intricate piece for a
   failure seen on first use), replacing the lint with a JSON Schema (cannot
   express unique ids, file name equals id or the budget, so a Python check
   would remain), dropping the lint (malformed definitions would become a
   generic 500 at runtime).
2. **Keep the contract test for the one mirrored limit.** `MAX_TEXT_CHARS` stays
   in `limits.py` and `lib.js`, guarded by `test_limits_contract.py` (26
   lines, regex over `var MAX_TEXT_CHARS = <n>;`). After decision 1,
   `limits.py` holds `MAX_BODY_BYTES`, `MAX_TEXT_CHARS` and `MAX_EMAIL_CHARS`;
   only the text limit is mirrored. Rejected: a shared `limits.json` fetched by
   the page and bundled into the function (more wiring than one number
   needs); dropping the mirror (the page has no message for
   `answer_too_long`, so drift would show a generic failure).
3. **Keep the symlink bundle.** `lambda/submit/polls` stays a symlink to
   `polls/`, bundled with `follow_symlinks=ALWAYS`; one source, two consumers
   (the function and the S3 `definitions/` deployment). Rejected: reading
   definitions from the site bucket at cold start (adds an S3 read grant, an
   environment variable, a cold-start call and a new failure mode, and needs
   deployment ordering care); copying `polls/` with a build step (allows drift
   and adds a Makefile step).

Consequences for other tickets:

- [Grill: test suite size and overlap](05-grill-test-suite-size.md): about 60
  fewer lines in `test_definitions.py`; the contract test stays.
- [Grill: submit handler structure](03-grill-handler-structure.md): the
  handler's per-type answer checks and its `parse_closes_at` import are
  unchanged by this decision; the Lambda package keeps `definitions.py` and
  `limits.py` side by side with `handler.py`.
