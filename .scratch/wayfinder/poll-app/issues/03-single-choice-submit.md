Status: ready-for-human
Type: HITL
Blocked by: 02

# 03. A single-choice poll accepts and stores a response

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The first complete write path. A Python submit function validates a single-choice submission against the poll definition (bundled from the same directory that feeds the site) and writes a response record. Adds the on-demand DynamoDB table (retained, deletion protection, point-in-time recovery off), the Function URL with IAM auth reached through the distribution's submit behavior using OAC, the shared limits constants, the page's submit with the body hash header and thank-you message, and an owner script that dumps one poll's responses. Node tests join the existing test gate and CI gets a Node setup step.

Human gate: deploy and verify the signed POST path on the real distribution.

## Acceptance criteria

- [x] Entry-point tests with an in-memory fake table: a valid submission returns a created response and writes exactly one response record holding answers by question ID, submitted-at time and poll version; response IDs sort by submission time.
- [x] Tests: an unknown option or a missing required answer is rejected with a machine-readable reason; an unknown poll returns not found; a body over 6 KB returns payload-too-large.
- [x] Page logic tests (Node built-in runner) cover the body hash with a known SHA-256 vector and the request body builder.
- [ ] CI's static-check runs the Node tests with a pinned Node setup.
- [x] Template assertions: the Function URL uses IAM auth, the table is retained with deletion protection, and the golden files are updated and read.
- [x] An owner script dumps one poll's responses to JSON or CSV using a single query.
- [x] After deploy: submitting through the page stores a record and shows a thank-you; a POST without the hash header fails; the raw function address is rejected; the table has the expected keys.

## Blocked by

- Blocked by 02

## User stories addressed

Spec user stories: 3, 12, 22, 34-37, 44-47, 64, 69, 72-74

## Comments

- 2026-10-16: claimed; proposing test seams to the owner before writing tests. Progress notes appended below.

### Progress (2026-10-16): code complete up to the human gate

Built test-first at the four seams confirmed with the owner. The dev gate (`make static`) and the CI gate (`make static-check`) both pass: pylint 10.00, 50 Python tests, 3 Node tests.

**Handler** (`lambda/submit`, 18 behavior tests with an in-memory table and fixed clock): `handle(event, table, definitions, now)` accepts only `POST /submit` (404 `not_found`, 405 `method_not_allowed`); rejects bodies over 6,144 bytes (413 `payload_too_large`, boundary tested on both sides), unparseable JSON (400 `invalid_json`), malformed requests (400 `invalid_request`: not an object, missing or mistyped fields, non-string answers), unknown polls (404 `unknown_poll`), unknown questions, missing answers and unknown options (400). A valid submission returns 201 `{responseId}` and stores one record: `pk` `POLL#<id>`, `sk` `RESPONSE#<ULID>`, `answers`, `submittedAt` (UTC), `pollVersion`. Response IDs are ULID-style (48-bit milliseconds plus 80 random bits, standard library only) and sort by submission time. `load_definitions` and the bundled `polls` symlink supply the definitions (a test submits against the real example poll). Limits live in `limits.py`. The deployed `handler` wiring (real clock, boto3 table from `TABLE_NAME`) is deliberately tiny glue with no unit test; it is exercised at the gate.

**Page**: `site/polls/lib.js` (works as a browser script and a Node module) with `sha256Hex` and `prepareSubmission`, tested against NIST vectors and an independently computed (Python `hashlib`) hash for the exact request body; `app.js` collects answers, signs and posts to `/submit`, shows a thank-you, and offers retry on failure (automatic retry arrives in slice 09). JS tests live under `tests/js`, outside the deployed folder, so test code is never uploaded; `make unit-test` runs them.

**Stack** (13 tests plus the exact-equality golden): on-demand table `natenite-production-polls-responses` (keys `pk`/`sk`, retained, deletion protection, no point-in-time recovery); Python 3.12 function (256 MB, 10 s) whose role allows only `dynamodb:PutItem` on that table; Function URL with `AWS_IAM`; a `/submit` behavior on the distribution (all methods, HTTPS only, caching disabled, origin request policy `AllViewerExceptHostHeader`) to the function through a Lambda OAC; both Lambda permissions for CloudFront (a regression guard for the library behavior found in the slice 01 spike). A test pins the bundle contents to exactly `handler.py`, `limits.py` and the real `polls/poll1.json` (it caught `__pycache__` bytecode, now excluded). The regenerated golden diff adds exactly the table, function, role and policy, URL, OAC and two permissions, and changes only the distribution.

**Owner script**: `scripts/dump_poll.py` (`make dump-poll poll=poll1`) pages through one query per poll and prints the responses as JSON; email records are excluded. Tested against a table that pages like DynamoDB, with `Decimal` numbers written as plain numbers.

**CI**: `.github/workflows/static-checks.yml` now sets up Node 22 before `make static-check`. Not yet seen running on GitHub; confirm on the first push.

Not done, needs the human (the gate):
- [ ] CI's static-check runs the Node tests with a pinned Node setup (configured and verified locally; unticked until a CI run is seen).
- [x] Log in (`aws sso login --profile mp-mgmt`), run `make diff-polls`, review (new table, function and role, URL, OAC, behavior), then `make deploy-polls`. CDK will prompt for the new IAM role.
- [x] After deploy: submitting through the page at `https://polls.natenite.net/poll1` shows the thank-you and stores a record; `make dump-poll poll=poll1` returns it; a POST without the `x-amz-content-sha256` header fails; the raw function URL is rejected; the table has `pk`/`sk` as expected.

### Gate run 1 (2026-10-16): deployed; 18 of 19 checks passed, one real defect found and fixed

The owner deployed and ran the temporary gate-check script (kept outside the repo). Passed: page, definition, HTTP-to-HTTPS redirect, main site unaffected; a valid signed submission returned 201 with a `responseId`; a POST without the hash header and one with a mismatched hash were both **403**; validation errors returned the expected status and reason (`unknown_option`, `missing_answer`, `unknown_question`, `unknown_poll`, `invalid_json`, 413 `payload_too_large` one byte over 6 KB); the raw function URL returned **403**; table settings (deletion protection, on-demand, `pk`/`sk`).

Failed: `make dump-poll` did not return the new record.
- **Cause (reproduced):** `NoRegionError`. The `mp-mgmt` profile has no region and `scripts/dump_poll.py` relied on an ambient one. boto3 ignores `AWS_REGION` (the check script exported that) and reads only `AWS_DEFAULT_REGION`; the check script also hid stderr, so the output said only 'not found'.
- **Fix (test-first):** new test `test_script_opens_the_environments_table_in_its_configured_region`; `open_table` takes the region from the environment's config, as the stack does. Verified against the real table with no region variable set (returns `[]`, the test record having been cleaned up). Gate: 51 Python tests, 3 Node tests, pylint 10.00.
- **Check script corrected:** exports `AWS_DEFAULT_REGION`, shows the last error line on failure, and the cleanup now uses `--return-values ALL_OLD`, because `delete-item` succeeds for a missing key and so could not prove the record had been stored.

Still open: re-run the script to confirm 19 of 19 (it proves the record was stored via the dump and via the returned deleted item), and the browser submission.

### Gate run 2 (2026-10-17 UTC): 19 of 19 checks passed

A genuine new run (new `responseId` `01M53JT5BCF7G1NHAF12ZCD3XF`) after the owner renewed the SSO login. (Two runs in between hit an expired SSO token; the script was changed to abort before any write when there is no session.) All checks passed, including the ones that failed or could not prove anything before:
- **Read path proven on real data:** `make dump-poll` returned the new record, so the region fix works against a real record, not only an empty table.
- **Existence proven:** the cleanup used `--return-values ALL_OLD` and got the item back, so the record had really been stored and was then deleted.
- **Sortable IDs encode real time:** decoding the three test IDs gives 2026-10-16 12:52:47 UTC, 2026-10-17 00:00:51 UTC and 2026-10-17 00:04:59 UTC (the last within 30 seconds of the wall clock when decoded), in increasing order.
- Signing enforced (403 for no or wrong hash), all validation reasons, 413 at one byte over 6 KB, the raw function URL forbidden, table settings.

Still open for this slice:
- [x] Browser submission through the page shows 'Thank you! Your response was recorded.' (not automatable).
- [x] Confirm the table holds no leftover test records from the earlier runs (`make dump-poll poll=poll1` should print `[]`): runs 1 and the failed-cleanup run created `01M52CBAXWGDHGWNNRBFABVMGA` and `01M53JJK7Y6R2WWMH0YE75VS1T`.
- [ ] CI's Node step is configured but not yet seen running on GitHub.

### Leftover test records cleaned up (2026-10-17 UTC)

The owner deleted the two earlier test records with `delete-item --return-values ALL_OLD`:
- `RESPONSE#01M53JJK7Y6R2WWMH0YE75VS1T` existed and was deleted. Its attributes are the first real production record seen: `pk` `POLL#poll1`, `sk` `RESPONSE#<ULID>`, `answers` `{q1: "a"}`, `submittedAt` `2026-10-17T00:00:51Z`, `pollVersion` `1`, no email record (correct until slice 06). The ULID's embedded time (00:00:51 UTC) agrees with `submittedAt` to the second.
- `RESPONSE#01M52CBAXWGDHGWNNRBFABVMGA` returned no attributes, meaning it did not exist: the first run's cleanup had in fact worked.

Struck from the open list above: the leftover-records item (pending only a final `make dump-poll poll=poll1` showing `[]`). Still open: the browser submission and the first CI run of the Node step.

### Table confirmed clean (2026-10-17 UTC)

`make dump-poll poll=poll1` printed `[]`: no response records remain, so no test data is left in production. This also means no browser submission has been made yet (it would have left a record), so that check is still outstanding along with the first CI run of the Node step.

### Browser check passed (2026-10-17 UTC)

The owner submitted through the page at `https://polls.natenite.net/poll1` and saw the thank-you message. With that, every acceptance criterion that can be checked before a push is met; the one remaining unticked criterion is the first CI run of the Node step (configured and verified locally, to be seen when the branch is pushed). Note: the owner's browser test may have left one real record in the table (`make dump-poll poll=poll1`).
