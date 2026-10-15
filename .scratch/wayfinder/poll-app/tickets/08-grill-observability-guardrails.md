---
type: grilling
status: open
claimed:
blocked_by: []
---

# Grill: observability and cost guardrails

## Question

Which CloudWatch alarms and budget guardrails does the polls stack define, and what do they notify? Decide with the human: alarms on function URL `Url4xxCount`/`Url5xxCount` and `Throttles`, `ConcurrentExecutions` at the reservation of 2 (the documented fallback if a throttled function URL request does not move the 4xx or throttle metrics), Lambda `Errors`, DynamoDB write failures (system errors, throttled requests), and WAF blocks from the rate rule (the ACL already emits CloudWatch metrics per rule); thresholds and evaluation periods; where notifications go (an SNS topic with an email subscription, or nothing); a budget alert for the account or the polls stack; log retention for the Lambda log group; and how alarms are covered by the golden test. Context: [Grill: abuse limits](06-grill-abuse-limits.md) (metric evidence and the open inference about 429 counting), [Grill: repo and deployment layout](07-grill-repo-deployment-layout.md) (alarms live in `stack/polls.py`), [Decide: architecture](04-decide-architecture.md), research/06 for unit prices.
