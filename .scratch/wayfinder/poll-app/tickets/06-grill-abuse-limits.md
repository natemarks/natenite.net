---
type: grilling
status: closed
claimed: nate (abuse limits session)
blocked_by: []
---

# Grill: abuse limits

## Question

What concrete limits protect the submit endpoint? Decide with the human: the per-IP WAF rate-based rule (requests per window, window length of 60/120/300/600 s, action: block or count first), the Lambda reserved concurrency cap (and therefore the function URL's maximum requests per second, 10 times that number), maximum request body size and free-text length, and what a respondent sees when throttled (429). Context: [Decide: architecture](04-decide-architecture.md) decisions 1 and 3, research/07 sections 7a and 7b, expected volume of 100 to 5,000 responses per poll.

## Resolution

Confirmed by the human at the end of the grilling session. Decisions:

1. **WAF rate rule:** one rate-based rule on the shared ACL, counting only `POST /submit` on the `polls.natenite.net` host (scope-down on Host, URI path and method), 20 requests per 300 s window per IP, action Block. Page loads do not count. About +$1/month. Accepted that a shared-IP group exceeding 20 submissions in 5 minutes is unlikely. Cites: research/07 section 7b (minimum limit 10; windows 60/120/300/600 s; not precise, detection lag usually under 30 s).
2. **Lambda reserved concurrency:** 2 (function URL maximum 20 requests per second; excess returns HTTP 429). Chosen on the human's condition that overruns can be monitored (see below). Accepted consequence: a burst above 20 requests per second loses those responses until the visitor retries.

### Can overruns be monitored? Yes, with one inference still to test

Documented (aws-docs MCP, pages read):
- **Function URL metrics** `UrlRequestCount`, `Url4xxCount`, `Url5xxCount` and `UrlRequestLatency`, with `FunctionName` and `Resource` dimensions; "you can monitor your function URLs, build dashboards, and configure alarms". https://docs.aws.amazon.com/lambda/latest/dg/urls-monitoring.html (section "CloudWatch metrics for function URLs"). A 429 is a 4XX status, so it should appear in `Url4xxCount`, but the page does not say 429 throttles are counted there. **Inference, not stated.**
- **`ConcurrentExecutions`** (1-minute granularity, view with MAX) shows active concurrent invocations per function, so an alarm at the reservation (2) detects saturation. https://docs.aws.amazon.com/lambda/latest/dg/monitoring-concurrency.html (section "General concurrency metrics").
- **`Throttles`** counts "invocation requests that are throttled" when no concurrency is available, and throttled requests are not counted in `Invocations` or `Errors`. https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html (section "Invocation metrics"). The page describes this for the invocation API (`TooManyRequestsException`); that function URL 429s also increment it is **not stated** (inference).
- The 429 behaviour and the 10x requests-per-second formula: https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html (section "Throttling function URLs").

Not verified in this pass: WAF `BlockedRequests` per-rule metrics (the repo's `SiteStack` ACL already sets `cloud_watch_metrics_enabled=True` on the ACL and its rules, a code observation), and CloudFront's own 4xx error-rate metric.

**Follow-up:** which alarms to create and their thresholds belongs to the observability fog item on the map. A test deploy should confirm whether a throttled function URL request increments `Url4xxCount` and/or `Throttles` before relying on either for alerting; `ConcurrentExecutions` at the reservation is the documented fallback.
3. **Throttled respondent experience (HTTP 429 from the function URL, WAF block, and 5xx):** the page retries automatically with backoff two or three times over a few seconds, keeping the form filled in; if retries fail it shows a friendly "busy, please try again in a minute" message with the answers preserved and a one-click resubmit.
4. **Size limits:** free-text answers capped at 500 characters; email at 254 characters; the Lambda rejects any request body over 6 KB (below the shared ACL's 8,192-byte `SizeRestrictions_BODY` limit, so respondents get a clear Lambda error instead of a generic WAF 403). A build-time check on poll definitions fails any poll whose worst-case body (up to 4 bytes per character plus overhead) could exceed the limit, which allows about three free-text questions per poll at 500 characters.

### Fact found while preparing decision 4 (shared ACL interaction)

The shared ACL attaches `AWSManagedRulesCommonRuleSet`, whose `SizeRestrictions_BODY` rule "Inspects for request bodies that are over 8 KB (8,192 bytes)" with action Block, and whose `NoUserAgent_HEADER` rule blocks requests with no `User-Agent`. Source: https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html (section "Core rule set (CRS) managed rule group"; the rules table was truncated at 5 of 22 rows, so other body-inspection rules were not read). Consequence: the submit body is capped at 8,192 bytes by the existing ACL regardless of what the Lambda allows, and free-text answers may also trip other managed body rules (false positives not checked; UNVERIFIED).

### Open risks carried forward

- Whether a function URL 429 increments `Url4xxCount` or `Throttles` is undocumented; confirm with a test deploy (fallback: `ConcurrentExecutions` at the reservation).
- Shared-ACL managed body rules may false-positive on free text (only 5 of 22 Core rule set rules were read); test free text with HTML-like characters once the stack exists.
- Reserved concurrency of 2 loses submissions above 20 requests per second; one-line change if a poll goes viral.
