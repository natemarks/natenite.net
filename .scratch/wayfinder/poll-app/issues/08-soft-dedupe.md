Status: ready-for-agent
Type: AFK
Blocked by: 03

# 08. Soft duplicate handling with a browser token

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The page generates a random browser token on first visit, remembers a prior submission and says so, and sends the token. The server stores it hashed on each response and never rejects repeats.

## Acceptance criteria

- [ ] Page tests (or manual check recorded in the PR): after submitting, reopening the poll in the same browser says it was already answered.
- [x] Entry-point tests: the token is stored hashed (never raw) on the response; two submissions with the same token are both accepted.
- [x] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 13, 38, 39

## Comments

- 2026-10-17: claimed; same seams as the earlier slices (handler entry point, page logic). Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; one item needs the owner

Built test-first at the confirmed seams. Gate: pylint 10.00, 242 Python tests, 28 Node tests; no golden file changed. (Before starting, the owner's deploy of slices 06 and 07 was verified from outside: live `poll2` is version 2 with no `closesAt` and all four question types, and a probe with valid answers and a bad email got `400 invalid_email`, so slice 06 is live and `poll2` is open. Nothing was stored by the probe.)

**Handler** (190 tests, up from 174): an optional `browserToken`.
- Present and exactly 32 lower-case hex characters: stored as `browserTokenHash`, the SHA-256 of the token in hex, on the response record. The expected hash is pinned against an independently computed (Python `hashlib`) value; the raw token appears nowhere in the stored items or in any response body.
- Missing: accepted, no hash stored (scripts and older cached pages keep working).
- Malformed (empty, too short or long, upper case, not hex, leading space, trailing newline, or not a string, including `null` and `true`): 400 `invalid_token`, nothing stored. Wrong types do not crash the function.
- Never rejects a repeat: the same token submitted twice is accepted twice, with two records carrying the same hash and different sort keys. (This and the missing-token case passed on arrival, as guards.)
- Validation order is answers, then token, then email.

**Page logic** (28 Node tests, up from 18), with storage and the random source injected: `newBrowserToken` (16 random bytes as 32 hex characters, pinned with known byte sequences); `getBrowserToken` (makes and keeps the token, never calls the random source again once stored, replaces a stored value that is not a token, and with blocked storage still returns a valid token for that page view); `rememberSubmission` / `previousSubmission` (per poll, with the time; garbage ignored; blocked storage tolerated); `answeredNotice` ('You already answered this poll in this browser on 2026-10-17. If someone else is using this browser, you can answer too.'); `prepareSubmission` now also sends the token (body order: pollId, answers, email if given, browserToken), its signed hash pinned against independently computed values with and without an email.

**Page** (DOM glue, not unit-tested): reading `window.localStorage` itself is guarded (it can throw); a returning browser sees the informational note above the form and **the form stays usable**; the token is sent with every submission; a successful submission, and the 'answers saved, email not saved' case, are remembered.

Not done:
- [x] After submitting, reopening the poll in the same browser says it was already answered (a real browser check; needs `make deploy-polls`). Suggested steps on `https://polls.natenite.net/poll1`: (1) open it in a normal window, submit, and see the thank-you; (2) reload: the note with today's date appears above a working form; (3) submit again: it is accepted; (4) `make dump-poll poll=poll1` should show two records with the same 64-character `browserTokenHash` and no raw token; (5) open the page in a private window: no note, and a different hash on a new submission; (6) in the browser's developer tools, Application > Local Storage shows `poll-browser-token` and `poll-answered:poll1`. Clean up the test records with `aws dynamodb delete-item --table-name natenite-production-polls-responses --return-values ALL_OLD --key '{"pk":{"S":"POLL#poll1"},"sk":{"S":"RESPONSE#<id from the dump>"}}'` for each, then confirm `make dump-poll poll=poll1` prints `[]`.

### Browser check passed and verified in the table (2026-10-17 UTC)

The owner confirmed the behavior in a browser. The table agrees: two records submitted 15 seconds apart (09:41:50Z and 09:42:05Z) carry the **same** 64-character lower-case-hex `browserTokenHash` (`088444db…b003`), so the token is stored only as its SHA-256 hash and a repeat from the same browser was accepted. The three older records have no hash because they predate this slice. All five response IDs decode to exactly the stored `submittedAt` second, in ascending order. Not evidenced by the data: a submission from a private window (only one distinct hash exists), which was checked by eye.

Separately, `make purge-emails days=0` (a dry run) found exactly one email record, `EMAIL#01M54HN5VG…` at 09:04:01Z, whose ID and timestamp match the first 09:04 response: the separate-record link from slice 06, confirmed on the real table, and the first live use of the maintenance script (it printed only the key and date).

Follow-up in the dump script (introduced in slice 03): its JSON now prints with sorted keys, because DynamoDB returns each record's attributes in no fixed order (the dump showed `browserTokenHash` first on some records and `answers` first on others). The same data now always gives the same text. Test-first: a record given in two different attribute orders must dump identically.
