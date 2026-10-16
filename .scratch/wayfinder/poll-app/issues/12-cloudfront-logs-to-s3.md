Status: ready-for-human
Type: HITL
Blocked by: 02

# 12. CloudFront access logs delivered to S3 (JSON, 365-day expiry)

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Configure CloudFront standard logging (v2) for the polls distribution to a new private S3 bucket in JSON, with a 365-day expiration rule and the bucket policy log delivery needs, using the log-delivery resources confirmed in slice 01.

Human gate: deploy and confirm logs actually arrive.

## Acceptance criteria

- [ ] Template assertions: delivery source, destination (S3, JSON) and delivery exist; the bucket is private with a 365-day expiration rule and a delivery policy.
- [ ] The golden file is updated and read.
- [ ] After deploy: log files appear in the bucket (allow several hours; delivery can lag up to 24 hours) and are JSON.
- [ ] Record whether a WAF-blocked request appears as a 403 with result type Error, and add the answer to the spec's further notes.

## Blocked by

- Blocked by 02

## User stories addressed

Spec user stories: 48, 49
