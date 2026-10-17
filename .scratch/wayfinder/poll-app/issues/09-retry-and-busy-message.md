Status: ready-for-agent
Type: AFK
Blocked by: 03

# 09. Retry with backoff and the friendly 'busy' message

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

On throttled (429) and server-error responses the page retries two or three times with backoff, keeps the answers in the form, then shows a 'busy, try again in a minute' message with a one-click resubmit. Validation errors are not retried.

## Acceptance criteria

- [x] Node tests cover the retry decision and backoff timing: 429 and 5xx retry, 4xx validation errors do not, and the number of attempts is bounded.
- [ ] The page keeps the form filled in after a failure and offers one-click resubmit.
- [ ] The message is shown for 429, WAF blocks and 5xx alike.
- [x] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 16, 17, 18, 19, 61

## Comments

- 2026-10-17: claimed; page-logic seam only (no handler change). Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; two items need the owner

Built test-first at the page-logic seam (no handler change). Gate: pylint 10.00, 243 Python tests, 41 Node tests (up from 28); no golden file changed. Before starting, the owner's cleanup was verified independently with read-only commands: no email records remain and all five responses are intact (including the one whose email was deleted), proving the purge removed only the address.

**Which outcomes retry** (`isRetryable`): 429, any 5xx, and network failures (a request that never got an answer). Not retried: 400-level validation errors, 403, 404, 405, 410, 413, and the one 500 that must never retry, `email_not_stored` (the answers are already saved, so a retry would store a duplicate). 403 is deliberately not retried (owner-approved recommendation): only the edge returns it (a WAF rate-limit block, which a few seconds' wait cannot lift, or a signing failure), but it still gets the friendly message.

**Timing:** at most 3 retries (4 attempts), waiting about 1s, 2s, 4s (`retryDelayMs`), each spread by up to 25% either way with an injected random source so tests pin the exact values (750 to 1250, 1500 to 2500, 3000 to 5000 ms) and visitors who hit a limit together do not all retry together.

**The loop** (`sendWithRetries`, with `send`, `sleep`, `random` and an `onRetry` callback injected, so no test waits): a first-try success makes one attempt and never waits; a throttled attempt recovers on the second; three retries then give up with waits [1000, 2000, 4000]; errors a retry cannot fix stop at once; a request that fails outright counts as a network error and is retried; the page is told of each wait before it happens.

**Busy and responses:** `isBusy` is true for retryable failures plus the edge's 403, and false when only the email was lost; `BUSY_MESSAGE` is 'The poll is busy right now. Your answers are still here. Please try again in a minute.'; `describeResponse` reads a response's status and, when the body is JSON with a text reason, the reason (the edge answers with HTML when it blocks a request, which falls back to the status alone).

**Page** (DOM glue, not unit-tested): the request is built and signed once and every attempt sends the same body with the same browser token; it shows 'Busy, trying again (N of 3)…' while waiting; after the last failure it re-enables the form with every answer in place, shows the busy message, and relabels the button 'Try again' (the one-click resubmit). Success, a closed poll and 'answers saved, email not' behave as before.

**Known limit:** if an attempt actually stored the response but the reply was lost (for example a gateway timeout after the function finished), the retry stores a second response. Both carry the same browser-token hash, so the owner's script can filter the repeat (soft dedupe, by design).

Not done:
- [ ] The page keeps the form filled in after a failure and offers one-click resubmit (real browser; needs `make deploy-polls`). Easiest way to cause a failure: on `https://polls.natenite.net/poll1`, answer the question, open the browser's developer tools, Network tab, set throttling to **Offline**, and press Submit. Expect 'Busy, trying again (1 of 3)…', then (2 of 3), then (3 of 3) over about 7 seconds, then the busy message with your answer still selected and the button now reading 'Try again'. Switch throttling back to 'No throttling' and press Try again: it should succeed with the thank-you. (Then delete the test record as before.)
- [ ] The message is shown for 429, WAF blocks and 5xx alike. Offline mode exercises the network path; a real 429 can be provoked once the concurrency cap exists (slice 10), and a WAF block once the rate rule exists (also slice 10), so the 429 and 403 paths are covered by the Node tests until then and should be re-checked live during slice 10.
