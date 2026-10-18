Status: ready-for-human
Type: HITL
Blocked by: 04, 05, 06, 07, 08, 09, 10, 11, 13

# 15. Launch verification: smoke tests, open inferences, privacy wording, real polls

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The final gate before announcing a poll. Run the end-to-end smoke tests from the build plan, answer the open questions from the research, and settle the launch checklist items that were deliberately left out of the architecture.

## Acceptance criteria

- [ ] All smoke tests from the build plan's first-deploy section have a recorded result.
- [ ] These open questions are answered in the spec's further notes: whether managed rules block ordinary free text; whether a throttled request moves the 4xx or throttle metric; whether WAF blocks appear as 403 in CloudFront logs; the status code used for a closed poll.
- [ ] The privacy notice wording is final, and a decision is recorded on whether any privacy regime applies to collecting an email.
- [ ] Real poll questions are in place, and the example poll is either kept or removed on purpose.
- [ ] The main site is confirmed unaffected.

## Blocked by

- Blocked by 04, 05, 06, 07, 08, 09, 10, 11, 13

## User stories addressed

Spec user stories: Verifies the stories above; closes the open inferences

## Launch checklist (working copy, 2026-10-18)

Sources: the build plan's P9 and P10, and what slices 1 to 14 verified live. "Verified" means seen live earlier in this build; items marked *confirm* are from my notes of earlier sessions and should be re-checked by you if unsure.

### A. Smoke tests (build plan P9)

| # | Test | State |
| --- | --- | --- |
| 1 | Page loads at `/poll1` | Verified (slices 3, 4) |
| 2 | Unknown poll ID shows "poll not found" | *Confirm* in a browser: open `/nope` |
| 3 | Real submission through the page; `RESPONSE#` record appears; `EMAIL#` when an address is given | Verified by API; *confirm* the browser path with an email |
| 4 | Email is not in the Lambda logs | Verified (slice 11 live probe); never logged by design |
| 5 | Raw `*.lambda-url` address rejected | Verified (slice 3 gate check, HTTP 403) |
| 6 | POST without `x-amz-content-sha256` fails; with it succeeds | Verified (slice 3 gate check) |
| 7 | Body over 6 KB gets the function's `payload_too_large` | Verified (slice 3 gate check, HTTP 413) |
| 8 | Body over 8 KB is blocked by WAF | **Open**: status and behaviour unverified |
| 9 | Free text with HTML-like characters is not blocked by the managed rules | **Open**: unverified; if blocked, decide on a Count override |
| 10 | Rate rule blocks more than 20 POSTs in 5 minutes from one address | Verified (slice 10); block duration not yet timed (`--measure`) |
| 11 | Throttling returns 429; which of `Url4xxCount`, `Throttles`, `ConcurrentExecutions` moves | **Deferred**: needs the Lambda quota raised and `reserved_concurrency` set |
| 12 | Access logs arrive; saved Athena queries run | Verified (slices 12, 13) |
| 13 | WAF blocks appear in the logs as 403 with result type `Error` | Answered (slice 12); in the spec's further notes |
| 14 | Closed poll status code | Decided 410 `poll_closed`, covered by unit tests; *confirm* live with a temporary poll whose `closesAt` is in the past |
| 15 | Main site (apex and `www`) unaffected | Checked by the rate-limit script; re-check at launch |

### B. Open questions to answer in the spec's further notes

- Managed rules on ordinary free text (A9).
- Throttled request and the 4xx or throttle metric (A11).
- Status for a closed poll (A14, once confirmed live).
- (Already answered: WAF blocks in the CloudFront logs.)

### C. Decisions for you

1. **Privacy notice wording.** Currently next to the email field: "Optional. We keep your address until you ask us to remove it." It says nothing about the access logs, which hold each visitor's IP address (kept a year), or about the answers. Decide whether to add a line, and where it lives (field notice or a page footer).
2. **Privacy regime.** Record whether any regime applies to collecting an email (the legal basis was never researched; I can't decide this for you).
3. **Real poll questions** in `polls/`.
4. **`poll1` and `poll2`**: keep live, or remove on purpose. Both are open to anyone who guesses the address.
5. **Leftover test data**: test responses remain in the table (six for `poll1` at last count); decide whether to remove them before launch.

### D. Housekeeping still open

- The old Lambda-created log group may need deleting (`delete-old-log-group.sh --yes`; its dry run passed).
- Browser checks not explicitly confirmed: slice 4, 5, 6 (partly) and 9 (offline mode, "Try again").
- Saved Logs Insights queries not yet run in the console.
- Extend the access-log table's year range (2026 to 2030) before 2031.
