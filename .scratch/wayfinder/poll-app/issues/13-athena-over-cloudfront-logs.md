Status: ready-for-agent
Type: AFK
Blocked by: 12

# 13. Athena table, workgroup and saved queries over the CloudFront logs

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Define the Glue database and table (partition projection per the AWS-documented JSON definition), an Athena workgroup with a results location that expires after about 30 days, and saved queries for errors by day, top client IPs, and 403 and 429 responses.

## Acceptance criteria

- [ ] Template assertions cover the table, workgroup, results expiration rule and the saved queries; the golden file is updated and read.
- [ ] After deploy and once logs exist: each saved query runs successfully against real delivered logs, and the results are recorded in the PR.
- [ ] `make static` passes.

## Blocked by

- Blocked by 12

## User stories addressed

Spec user stories: 50, 51, 57
