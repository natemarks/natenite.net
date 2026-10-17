Status: ready-for-human
Type: HITL
Blocked by: 03

# 10. Rate rule on the shared ACL and Lambda concurrency cap of 2

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Add the per-IP rate-based rule to the existing shared web ACL (counts only POST to the submit path on the polls hostname, 20 per 5 minutes, action block) and set the function's reserved concurrency from settings. This edits the live main-site ACL.

Human gate: review the Site diff in isolation, deploy, and run the throttling checks.

## Acceptance criteria

- [x] The Site golden file changes only by the new rate rule, and template assertions confirm its scope (host, path, method), limit, window and action.
- [x] The function's reserved concurrency is read from the polls settings and asserted in the template.
- [ ] After deploy: more than 20 submit POSTs from one IP in 5 minutes are blocked; page views are not counted; driving concurrency above the cap returns HTTP 429.
- [ ] While testing, record which of Url4xxCount, Throttles and ConcurrentExecutions moved for a throttled request, and add the answer to the spec's further notes.
- [ ] The main site (apex and www) is unaffected.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 58, 59, 60, 61, 65

## Comments

- 2026-10-17: claimed. Plan confirmed with the owner: rate rule at priority 0 (20 per 300 s per IP, Block, scope host+path+method); reservation optional in settings because the account quota is 10 (reserving needs it raised to over 100); the 429 live test waits for the quota. Seams: settings loading and the stack templates.

### Progress (2026-10-17): code complete; the live checks need the owner

Built test-first at the confirmed seams (settings loading, the Site and Polls stack templates). Gate: pylint 10.00, 267 Python tests, 41 Node tests. Only the Site golden changed.

**A finding that changed the plan (read-only checks against the real account):** the account's Lambda concurrent-executions quota is **10** (the default for an account is 1,000; the quota is adjustable and no increase had been requested). Lambda lets you reserve at most the unreserved account concurrency minus 100 (https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html), so on this account *no* reservation can be made, and the decided 'reserved concurrency of 2' cannot be applied yet. The owner chose to leave the quota alone: the account's 10 is itself a free ceiling on concurrent executions (roughly 5 times the cap of 2, still small in cost), and raising the quota to 1,000 *without* also reserving 2 would loosen that ceiling about 100 times, so the two changes only make sense together. Consequences recorded: `reserved_concurrency` is an **optional** polls setting (unset in production: no reservation is created, so the deploy works); to apply the cap later, request the quota increase (`aws service-quotas request-service-quota-increase --service-code lambda --quota-code L-B99A9384 --desired-value 1000`), then add `"reserved_concurrency": 2` to `config/production/polls/polls.json` and deploy. A throttled request never runs the function, so the function's own log line cannot show throttling; it shows in Lambda's `Throttles` metric and, once slices 12 and 13 exist, as 429s in the CloudFront logs.

**Settings:** `PollsSetting` gains `rate_limit` (20) and `rate_window_seconds` (300), both required, and `reserved_concurrency` (optional, default unset). `SiteInput` now loads the polls settings and computes the polls host.

**The rule** (Site stack, first in the shared ACL, priority 0, named `PollsSubmitRateLimit`): counts only requests where the lower-cased `host` header is exactly the polls host AND the path is exactly `/submit` AND the method is `POST`, aggregated per IP, 20 per 300 seconds, action Block, CloudWatch metrics and sampled requests on. The two managed rule groups keep priorities 1 and 2 and are byte-for-byte unchanged. Tests: the full rule shape; the host, limit and window all come from settings (a custom 'vote' / 30 / 120 flows through); the priorities; and a cross-stack guard that the rule's host, path and method match what the polls distribution serves (proven able to fail by changing the rule's path).

**A real bug the tests caught before any deploy:** WAF's `SingleHeader` field is untyped JSON in CDK, so a key written `name` is passed through verbatim, and CloudFormation requires `Name` (CDK's own validation warned: `'Name' is a required property`). Even the typed property class rendered lowercase. It is written `{"Name": "host"}` with a comment, and the test pins the exact CloudFormation spelling. Without that test the Site stack update would have been rejected at deploy time.

**Site golden test is now exact equality** (it used the loose `template_matches`, which ignores extra sections and properties, so it could not have noticed an unintended change to the shared ACL). Diff of the regenerated golden, read: only the `Rules` of the one ACL changed; the new rule is first; the two existing rules are identical; no other resource or section moved.

**Function:** `reserved_concurrent_executions` comes from the polls settings; tests cover unset (production: the property is absent) and set to 2 (it appears). The polls golden did not change.

Not done (needs the owner):
- [ ] Review the Site diff in isolation (`make diff-polls`; the shared ACL gains one rule, nothing else), then `make deploy-polls`. A change to a rate rule's settings resets its counts and can pause limiting for up to a minute.
- [ ] After deploy, the rate check: send 25 quick signed POSTs to `/submit` that are rejected before storing anything (an unknown option, so nothing is written). Expect the first 20 to return `400` and the rest `403` from WAF; GETs of the page and the main site must be unaffected throughout; the block should last roughly until the burst ages out of the 5-minute window (my expectation: record how long it really lasts). Check the rule's blocked count in the WAF console (sampled requests) or CloudWatch.
- [ ] The 429 / `Throttles` check is **deferred** until the quota is raised and a reservation is set (about 15 parallel requests, under the 20 per 5 minutes so WAF does not block them first); record then which of `Url4xxCount`, `Throttles` and `ConcurrentExecutions` moved, and add it to the spec's further notes.

### Live rate check run (2026-10-17 UTC): the rule works; how it behaves is not what a naive reading of '20 per 5 minutes' suggests

The owner deployed slice 10 (found when a script run for another purpose showed the rule already live) and ran the throw-away check. Results, cross-checked against WAF's own numbers:
- **The rule is deployed exactly as designed** (read from WAF itself): attached to the polls distribution's ACL; priority 0; limit 20; window 300 s; per IP; Block; host (lower-cased) `polls.natenite.net`, path `/submit` exactly, method `POST`.
- **A sustained stream is blocked.** About 4 signed POSTs per second (each rejected before storing anything): 51 returned `400`, then the 52nd, **23 seconds into the stream**, returned `403` with WAF's block page, and the next 19 did too (the script stopped after 20 in a row). WAF's own metric agrees: `BlockedRequests` for the rule is exactly **20**, in the same minute; the ACL's allowed count adds up to the 61 requests that were allowed (3 baseline GETs, 1 baseline POST, 51 passed POSTs, 6 GETs while blocked).
- **Only POSTs to `/submit` are limited.** While blocked: the poll page, the definition, `app.js`, `natenite.net` and `www` all returned 200, and a `GET /submit` reached the function (405 `method_not_allowed`). Nothing was stored (6 records before and after, 71 rejected requests).
- **The limit is not a hard 20.** Because WAF's rate estimate lags and favours recent requests (AWS documents this: usually under 30 s, sometimes minutes), about 50 requests got through before the block, roughly the limit plus the detection delay times the request rate (23 s at 4 per second). A sustained flood is stopped within about half a minute; a person submitting once is nowhere near it.
- **A short spike is not caught.** An earlier accidental run sent 61 requests in 10 seconds and then stopped: WAF let all of them through and never flagged the address, even after 8 minutes of watching. Consistent with the recency weighting: the rule defends against sustained floods (which is what costs money), not against a one-off burst of a few hundred requests, which is cheap.
- **The block appears to lift quickly.** About a minute and a half after the stream ended, the list of limited addresses was already empty. The expectation written earlier (a block lasting nearly the full 5-minute window) looks wrong; the exact release time is not yet measured (`--measure` in the script, after waiting).

Corrections to my own earlier steps in this session, for the record: I ran the script once without checking the rule was deployed (it sent 61 rejected requests; nothing stored); a read-only watcher printed a false 'rate limiting detected' when the owner's connection dropped (an empty answer was misread as a detection); and I queried WAF metrics with a `Region` dimension that does not exist (the metrics have only `WebACL` and `Rule`), so they looked empty. The script's own metrics section had the same mistake and was fixed.

Open: the 429 / `Throttles` check stays deferred until the quota is raised and a reservation is set (see above); and, optionally, timing the block's release with `--measure`.
