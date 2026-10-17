Status: ready-for-agent
Type: AFK
Blocked by: 12

# 13. Athena table, workgroup and saved queries over the CloudFront logs

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Define the Glue database and table (partition projection per the AWS-documented JSON definition), an Athena workgroup with a results location that expires after about 30 days, and saved queries for errors by day, top client IPs, and 403 and 429 responses.

## Acceptance criteria

- [x] Template assertions cover the table, workgroup, results expiration rule and the saved queries; the golden file is updated and read.
- [x] After deploy and once logs exist: each saved query runs successfully against real delivered logs, and the results are recorded in the PR.
- [x] `make static` passes.

## Blocked by

- Blocked by 12

## User stories addressed

Spec user stories: 50, 51, 57

## Comments

- 2026-10-17: template, golden and tests done (new module `stack/polls_access_log_queries.py`). The log bucket now has two rules: `cloudfront/polls/` 365 days, `athena-results/` 30 days. Queries: `polls/errors-by-day`, `polls/top-client-addresses`, `polls/blocked-and-throttled` (403 and 429). Still to do after deploy: run each saved query in the Athena console against real logs.
- 2026-10-17: the first live run hung: projecting year x month x day x hour (about 187,000 folders) made Athena plan for minutes. Dropped the hour folder from the delivery (suffix `{yyyy}/{MM}/{dd}`) and bounded the year range (2026 to 2030, about 1,860 folders); a test now caps the count at 2,000. Extend the year range before 2031. Files delivered under the old hourly layout are not read by the table.
- 2026-10-17: verified live with `make query-logs` (90 days): all three saved queries ran against real delivered logs, columns read through the SerDe mapping, partitions projected quickly. Results agreed with each other: 43 x 400 + 20 x 403 + 1 x 405 = 64 rejected, of 119 requests from one address (the owner). 20 WAF blocks listed, no 429s (no reservation, as expected). Only files in the daily layout are counted: earlier flat and hourly test files are not read.
