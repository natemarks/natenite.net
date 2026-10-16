Status: ready-for-agent
Type: AFK
Blocked by: 03

# 09. Retry with backoff and the friendly 'busy' message

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

On throttled (429) and server-error responses the page retries two or three times with backoff, keeps the answers in the form, then shows a 'busy, try again in a minute' message with a one-click resubmit. Validation errors are not retried.

## Acceptance criteria

- [ ] Node tests cover the retry decision and backoff timing: 429 and 5xx retry, 4xx validation errors do not, and the number of attempts is bounded.
- [ ] The page keeps the form filled in after a failure and offers one-click resubmit.
- [ ] The message is shown for 429, WAF blocks and 5xx alike.
- [ ] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 16, 17, 18, 19, 61
