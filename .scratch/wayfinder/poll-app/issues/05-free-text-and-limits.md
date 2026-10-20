Status: ready-for-agent
Type: AFK
Blocked by: 03

# 05. Free-text answers with length and body-size limits

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Add free-text questions capped at 500 characters, with a live remaining-characters count, and make the oversize-body rejection give respondents a clear message instead of a generic block.

## Acceptance criteria

- [x] Entry-point tests: an answer over 500 characters is rejected with a reason; a body over 6 KB is rejected with payload-too-large before the shared ACL's 8 KB limit applies.
- [ ] The page shows a remaining-characters count and a clear message when a limit is hit.
- [x] Limits come from the shared constants, not duplicated values.
- [x] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 6, 7, 62, 63

## Comments

- 2026-10-17: claimed; same seams as slices 03 and 04. Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; one item needs the owner

Built test-first at the confirmed seams. Gate: pylint 10.00, 93 Python tests, 11 Node tests; no golden file changed.

**Handler** (59 tests, up from 45): free-text questions (`"type": "text"`) are required. In order: not a string is `invalid_answer`; blank or whitespace-only is `missing_answer`; longer than 500 characters is `answer_too_long`. The cap counts Unicode characters, not bytes or UTF-16 units: 500 each of `x`, `é` and an emoji outside the BMP are accepted, 501 are rejected. The answer is stored exactly as typed. The 6 KB body limit and its `413` shipped in slice 03 and still pass. The test helper now builds bodies the way a browser's `JSON.stringify` does (no `\uXXXX` escaping of non-ASCII), because Python's default escaping made a 500-emoji body exceed the 6 KB limit and would have failed for the wrong reason.

**Page logic** (11 Node tests, up from 7): `textLength` counts code points (`"😀".length` is 2 in JavaScript, 1 here, as on the server), `charactersLeft`, `missingQuestions` now treats whitespace-only text as unanswered, and `overLimitQuestions`.

**Limits, one source guarded by a test** (the owner chose a literal in the page library plus a drift test over generating a `limits.json` at deploy time): `limits.MAX_TEXT_CHARS = 500` is authoritative; `lib.js` keeps `var MAX_TEXT_CHARS = 500;`; `test_page_library_text_limit_matches_the_function_limit` fails if they differ (proven by temporarily setting the page value to 499, which failed with `499 == 500`, then restoring it).

**Page** (DOM glue, not unit-tested): a textarea with a live counter ('N characters left', then 'N characters over the limit' in red, with a dark-mode colour); no `maxlength` attribute, because it counts UTF-16 units and would cut emoji text short; submitting is blocked with 'Please shorten your answer: the limit is 500 characters.'

**Example poll**: `polls/poll2.json` gains a free-text question `q4` and its version goes to 2. (The bundled-polls test went red first because its helper did not know the `text` type, then green.)

Not done:
- [ ] The page shows the counter and the limit message (needs `make deploy-polls`, then `https://polls.natenite.net/poll2` in a browser: type to watch the counter count down, paste more than 500 characters to see it go over and block submitting, try emoji (each counts once), try leaving the box blank).
