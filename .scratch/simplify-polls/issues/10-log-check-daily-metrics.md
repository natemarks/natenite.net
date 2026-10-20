Status: ready-for-human
Type: HITL
Blocked by: 09

# 10. Log check part 2: daily metrics

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Add the second half of the log check. A stored metric query definition and `make fetch-metrics [days=90]` download daily totals for firewall blocked requests by rule, function errors and throttles, and the distribution's error rate into the working folder, and a second stored jq program summarises them per day; `make check-polls` runs both fetches and prints one combined summary. Daily resolution is required because finer data is only retained for a short time. The exact metric names and dimensions, notably for firewall metrics on a CloudFront-scoped web ACL, are unverified: a human confirms them against the real account. A fixture test covers the metrics summary. See [Grill: owner scripts and docs](../tickets/06-grill-owner-scripts-and-docs.md), decision 1.

## Acceptance criteria

- [x] The metric names and dimensions are confirmed against the real account (for example with `aws cloudwatch list-metrics`) and recorded in the PR with how they were checked.
- [x] `make fetch-metrics` takes `days` defaulting to 90, uses daily periods, and changes nothing in AWS.
- [x] A fixture test asserts the per-day metrics summary and runs in the unit-test gate.
- [x] `make check-polls` prints one summary combining log and metric results.
- [ ] A human runs it against production and confirms one day's numbers match the console. (Left open for you: see the comment below for the day and the numbers to compare.)
- [x] `make static` passes.

## Blocked by

- Blocked by [Log check part 1: errors and rejections from the function's log](09-log-check-errors-and-rejections.md)

## User stories addressed

Spec user stories: 1, 4, 5, 6, 7, 36

## Comments

Done except the human console comparison (uncommitted). New files:
`scripts/jq/polls_metric_queries.jq`, `scripts/jq/polls_metrics_summary.jq`.
Changed: `Makefile`, `stack/polls.py` (a `PollsInput.stack_name()` method the
stack now uses for its own id, so no template change), and the fixture tests in
`tests/unit/scripts/test_polls_log_check.py` (12 new tests).

**Confirmed against the production account** (read-only calls, profile
`mp-mgmt`, account 605560722292, us-east-1), with the AWS docs for the
namespaces:

| Series | Namespace, metric, dimensions | Stat |
|---|---|---|
| Firewall blocks by rule (shared ACL, so also the main site) | `AWS/WAFV2` `BlockedRequests`, dims `Rule` + `WebACL`; rules seen: `ALL`, `AWSManagedRulesCommonRuleSet`, `AWSManagedRulesKnownBadInputsRuleSet`, `PollsSubmitRateLimit`. No `Region` dimension, as the docs say for CloudFront. | Sum |
| Firewall blocks on the polls site only | `AWS/WAFV2` `BlockedRequests`, dims `Resource` (the distribution's ARN) + `ResourceType=CF` | Sum |
| Function | `AWS/Lambda` `Invocations`, `Errors`, `Throttles`, dim `FunctionName` | Sum |
| Distribution | `AWS/CloudFront` `Requests`; `4xxErrorRate`, `5xxErrorRate`; dims `DistributionId` + `Region=Global` | Sum; Average |

- **Generated names:** the `WebACL` dimension is `NateNiteProductionSiteWebACL-<suffix>`
  (not the name in the code), the function name is generated, and so is the
  distribution ID. The fetch finds the function and distribution from the
  deployed stack (`describe-stack-resources`, the submit function chosen by its
  logical-ID prefix) and matches the ACL as a search term on its known prefix.
  The search expression, the dynamic labels (`${PROP('Dim.Rule')}`) and the
  daily period all worked live; every series came back `Complete`.
- **Bug the live run caught:** the CLI writes timestamps in the machine's own
  timezone (the day starting `2026-10-17T00:00:00Z` came back as
  `2026-10-16T20:00:00-04:00`). The summary converts every timestamp to UTC
  itself, so the answer does not depend on the machine's timezone; the tests
  cover `-04:00`, `+00:00`, `Z`, `+05:30`, and an offset that moves the UTC day
  to the day before.
- **Independent cross-check, 2026-10-17 UTC, via `get-metric-statistics`:**
  invocations 250, errors 0, distribution requests 450. Same as the summary.
- **Additions to the plan:** labels say whether a series is the shared ACL or
  the polls site, each series names its peak day (`max_day`), and the summary
  also reports the CloudFront 4xx rate, which includes firewall 403s, and
  invocations and distribution requests so a rate is not read without its
  volume. A day missing from a series means no data (zero).
- **Tests:** 12 new fixture tests (query definition: ids, namespaces, metric
  names, dimensions, stats, the search expression, daily periods, label
  prefixes; summary: UTC days, counts versus rates, merging pages by label,
  search results sharing an id, incomplete series, empty input). A mutation run
  broke the programs 17 ways and caught 16; the one miss (dropping the explicit
  final sort) is an equivalent change, since `group_by` already orders by
  label.
- `make static` and `make static-check` exit 0: pylint 10.00/10, 267 Python
  tests (255 before, plus 12) and 41 Node tests.

**Targets:** `make -s fetch-metrics [days=90]` writes
`.polls-check/metrics.json` (UTC midnight to now, daily). `make -s check-polls
[days=90]` now runs both fetches and prints one document with `logs`,
`metrics` and `incomplete_metrics`. `fetch-logs` and `fetch-metrics` share one
lookup of the stack's names (`POLLS_NAMES` in the Makefile), so no formula is
repeated.

**Verified live now:** `make -s fetch-metrics` against production, the summary
over the real response, the real log-event shape (`events[].timestamp` and
`.message`, one merged document, platform lines such as `INIT_START` skipped),
and the combined summary over real log and metric files (228 log lines: 2
accepted, 223 `unknown_option` and 3 `method_not_allowed` rejections, all on
2026-10-17; likely the earlier throttling tests, which is an inference).

**Not verified yet:** a full `make -s check-polls` end to end. `fetch-logs`
looks for the pinned log group `/natenite/production/polls/submit`, which does
not exist until the stack is redeployed (the deployed group still has its
generated name); today it fails cleanly with exit non-zero and no summary. The
deploy slice covers it.

**For you (the open criterion), a day to compare in the CloudWatch console,
2026-10-17 UTC, us-east-1:** function invocations 250, errors 0, throttles 0;
the polls distribution (E306UP7NR8ESLA) requests 450, 4xx 67.3 percent, 5xx 0;
`PollsSubmitRateLimit` blocked 60, the same 60 as the polls-site total. Run
`make -s fetch-metrics` and `jq -s -f scripts/jq/polls_metrics_summary.jq
.polls-check/metrics.json` to see the full output.
