Status: ready-for-agent
Type: AFK
Blocked by: 03

# 06. Optional email stored as a separate record, with the privacy notice

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Add the optional email field. When given, store it as its own record linked to the response by response ID; when omitted, store nothing. The email is never written to logs. The page shows a one-line notice that the address is kept until removal is requested (final legal wording is out of scope). Extend the owner script with 'purge emails older than N days' and 'delete by email address'.

## Acceptance criteria

- [x] Entry-point tests: no email means no email record; a valid email creates an email record with the same response ID as the response; an invalid or over-254-character email is rejected with a reason.
- [x] A test confirms no log output from the handler contains an email address.
- [ ] The page shows the optional email field and the one-line notice; skipping it works.
- [x] The owner script purges emails older than a given age and deletes by address, with tests against the fake table.
- [x] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 8, 9, 10, 40, 41, 42, 43, 53

## Comments

- 2026-10-17: claimed; same seams as the earlier handler slices, plus a new owner-script seam. Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; one item needs the owner

Built test-first at the confirmed seams (handler entry point, page logic, and a new owner-script seam). Gate: pylint 10.00, 227 Python tests, 18 Node tests; no golden file changed.

**Handler** (174 tests, up from 143): an optional `email` field.
- Missing, empty or whitespace-only: no email record, nothing else changes. A non-string (including `null`) is `invalid_email`.
- Trimmed, then at most 254 characters (`email_too_long`, checked first so junk of any length says too long), then a deliberately pragmatic shape (`invalid_email`): one `@`, text on both sides, a dot inside the domain with no empty parts, no whitespace. A hole found while writing it: `reader@example..com` (two dots) got through the first regex and was caught by a test written to prove it. Real-world shapes pass (plus-addressing, subdomains, non-ASCII letters); case is kept.
- A rejected email stores nothing, not even the answers.
- A valid email is stored as its own record: same poll key, sort key `EMAIL#<the response's ID>`, `email`, and the same `submittedAt`. The response record never contains the address.
- Write order: the response first, then the email. If the email write fails (`ClientError`), the answers stay and the visitor gets HTTP 500 `email_not_stored`, without the address in the body.
- Privacy test: accepted, rejected, too-long and failed-write submissions leave no trace of the address in logs, printed output or response bodies. Proven able to fail: temporarily printing the request body made it fail; the handler was restored (no `print` remains).
- `MAX_EMAIL_CHARS = 254` joins the shared limits.

**Owner script** (`scripts/manage_emails.py`, 22 script tests): `purge --older-than-days N` and `delete --email ADDRESS`, both a **dry run unless `--yes`**. Purge is strictly older than N days (a record exactly N days old stays; a negative, fractional or non-numeric age is refused). Delete matches ignoring case and surrounding spaces, across all polls; a blank address is refused so it can never match everything. Both follow every page of the scan, never touch response records, and report only keys and dates, never addresses. New make targets: `make purge-emails days=365 [yes=1]` and `make delete-email email=a@b.co [yes=1]`. `dump_poll` still excludes emails.

**Page logic** (18 Node tests, up from 14): `prepareSubmission(pollId, answers, email)` adds a trimmed email and omits a blank one (the signed hash of the exact body is checked against an independently computed value); `rejectionMessage` explains `invalid_email` and `email_too_long`, and `email_not_stored` ('Thank you! Your answers were saved, but we could not save your email address.').

**Page** (DOM glue, not unit-tested): an optional 'Email (optional)' field named `respondent-email` (question IDs cannot contain hyphens, so it can never collide with one) and the placeholder notice 'Optional. We keep your address until you ask us to remove it.' (final wording is a launch item). A rejection the respondent can fix shows its specific message and re-enables the form; `email_not_stored` ends the flow so a retry does not duplicate the saved response.

Not done:
- [ ] The page shows the optional email field and notice, and skipping it works. Needs `make deploy-polls`, then on `https://polls.natenite.net/poll1` (poll2 may still carry your closed-poll experiment): (1) submit without an email; (2) submit with one; (3) try a bad address such as `nope@` and expect 'Please check your email address.' with the form still filled in. Then confirm in the table: `aws dynamodb query --table-name natenite-production-polls-responses --key-condition-expression 'pk = :pk AND begins_with(sk, :p)' --expression-attribute-values '{":pk":{"S":"POLL#poll1"},":p":{"S":"EMAIL#"}}'` should show your address once. Clean up with the new script: `make delete-email email=you@example.com` (dry run, lists the key), then `make delete-email email=you@example.com yes=1`, then `make dump-poll poll=poll1` and the query again to confirm it is gone. This also exercises the delete script on the real table.
