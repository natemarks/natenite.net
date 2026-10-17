Status: ready-for-agent
Type: AFK
Blocked by: 03

# 07. Poll closing time and a test that validates every poll file

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Enforce an optional closing time (UTC) on the server and show a 'poll closed' message in the page. Add a unit test that loads every real poll definition file and fails a bad one, including checking that the worst-case submission size stays within the limit.

## Acceptance criteria

- [x] Entry-point tests with a fixed clock: a submission before the closing time is accepted; after it is rejected with a distinct reason; a poll without a closing time never closes. The status code chosen for a closed poll is documented in the tests.
- [ ] The page shows a 'poll closed' message.
- [x] A test runs every file in the poll definitions directory and checks valid question types, unique IDs, a valid closing time, rating bounds, an integer version, and that the worst-case body (up to 4 bytes per character for every free-text cap, plus email and overhead) is under the 6 KB limit.
- [x] A deliberately bad poll file makes the test fail (shown in the PR), and the test runs in the normal unit-test gate.
- [x] The version number is stored on every response.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 15, 27, 28, 29, 30, 31

## Comments

- 2026-10-17: claimed; same seams as slices 03 to 05, plus the poll-definition check function. Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; one item needs the owner

Built test-first at the confirmed seams (handler entry point, the new definition checks, page logic). Gate: pylint 10.00, 176 Python tests, 14 Node tests; no golden file changed.

**Closing time** (handler, 66 tests): an optional `closesAt` in UTC (`2026-12-31T23:59:59Z`, only the `Z` form). A poll is closed **at** that instant (`>=`): a submission at, one second after, or long after the closing time returns **HTTP 410** with reason `poll_closed`; one second before is accepted; a poll without `closesAt` never closes. 410 was chosen over 403 because CloudFront and OAC already use 403 for signing failures. The closed check comes before the answer checks, so a closed poll reports `poll_closed` even when the answers are also wrong. A mutation check confirmed the boundary is pinned: changing `>=` to `>` fails the at-the-instant test.

**Poll definition checks** (`lambda/submit/definitions.py`, 77 tests): `validate(definition, file_stem)` returns a list of problems. Rules: the file name equals the `id`, which is lower-case letters, digits and hyphens (the page fetches `/definitions/<id>.json`); `version` a whole number of at least 1 (booleans and floats rejected); non-empty title and prompts; at least one question, unique IDs matching `[a-z][a-z0-9_]*`, type one of `single`, `multi`, `rating`, `text`; choice questions have two or more options with unique non-empty string IDs and non-blank labels; rating `min` and `max` are whole numbers with `min` below `max` and at most 10 steps apart (the page draws one button per value; the 10 was an owner-approved choice); `closesAt` must parse. The handler now uses the checker's single `parse_closes_at`.

**Worst-case size budget:** `worst_case_body_bytes` builds the largest submission a poll allows (longest option for single choice, every option for multiple choice, the widest rating, 500 four-byte characters per free-text answer, compact JSON) and the check requires that plus `limits.RESERVED_BODY_BYTES` (1,536 bytes for the email, browser token and envelope the later slices add) to fit within `MAX_BODY_BYTES` (6,144). The expected size is pinned against a hand-built string, independent of the code.

**Correction to an earlier statement:** the confirmation message said this budget allows 'about three' 500-character free-text questions per poll. It allows **two**: each is 2,000 bytes, and 6,144 - 1,536 = 4,608 leaves room for two, not three (three would not fit even with no reservation at all). Tests pin both: two fit, three are rejected by the check. The options if three are wanted: raise `MAX_BODY_BYTES` (the shared ACL blocks bodies over 8,192 bytes, so there is limited headroom), shrink the reservation, or accept two. Real worst cases can also exceed 4 bytes per character: text made of control characters or quotes expands up to 6 bytes per character once JSON-escaped, in which case the respondent gets a clean `413`, never a crash.

**Every real poll file is checked** (`test_every_poll_definition_in_the_repository_is_valid`, one case per file in `polls/`, plus a guard that files exist). A deliberately bad file was added to show it fails, then removed. It failed with:

    zz-bad.json has problems:
    - file name 'zz-bad.json' must match the id 'something-else'
    - version must be a whole number of at least 1
    - closesAt must look like 2026-12-31T23:59:59Z (UTC)

(The size problem for its three text questions appears once the structural ones are fixed: the size check runs only on a structurally valid poll, so a malformed file gets a clear list and not a crash.)

**Page:** new tested `isClosed(definition, nowMs)` (an unreadable `closesAt` is left to the server); the page shows 'This poll is closed.' instead of the form when the visitor's clock says so, and also when the server answers 410 on submit.

**Also changed:** the bundle-contents test now expects `definitions.py` in the deployed function (the handler imports it); it caught that the new module had to be in the bundle, and confirmed it is.

Not done:
- [ ] The page shows 'This poll is closed.' (needs a deploy and a browser). Easiest check: temporarily set `"closesAt": "2020-01-01T00:00:00Z"` in `polls/poll2.json`, `make deploy-polls`, open `https://polls.natenite.net/poll2` and expect the message instead of the form, then remove the line and redeploy. A submission to a closed poll can also be tried with the signed `curl` from the gate-check script and should return 410 `poll_closed`.

### Found while checking the closed-poll page (2026-10-17): tests assumed polls never close

The owner set `"closesAt": "2020-01-01T00:00:00Z"` in `polls/poll2.json` to check the 'This poll is closed.' page. `make deploy-polls` runs the unit tests first and stopped (nothing was deployed): `test_every_bundled_poll_accepts_a_valid_submission[poll2]` failed with `410 == 201`.
- **Cause:** a flaw in a test written in slice 04, before closing times existed and not revisited in slice 07. It submitted to every poll in the repository at a fixed moment (2026-10-16) and expected acceptance. The server was right to answer 410 `poll_closed`; the test was wrong. As written, any poll that legitimately reached its closing date would have failed the unit gate and blocked every deploy, including unrelated ones.
- **Fix:** both tests that submit to real poll files now submit while the poll is open (`open_time_for`: one second before `closesAt`, or the fixed time when there is none). Verified with the closed `poll2` still in place: 176 Python tests, 14 Node tests, pylint 10.00, no golden change.
- **Lesson recorded:** checks over the polls in the repository must not assume a poll is open now; polls closing is the feature.

### Decision (2026-10-17): keep two free-text questions per poll

The owner reviewed the size-budget correction (two 500-character free-text questions fit, three do not) and chose to keep it: little free text is expected, and a limited implementation keeps the project simpler. No change to the 6 KB body limit or the 1.5 KB reservation. Also recorded in the spec's further notes.
