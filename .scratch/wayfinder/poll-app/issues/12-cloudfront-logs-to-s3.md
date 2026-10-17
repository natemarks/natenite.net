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

- [x] Template assertions: delivery source, destination (S3, JSON) and delivery exist; the bucket is private with a 365-day expiration rule and a delivery policy.
- [x] The golden file is updated and read.
- [x] After deploy: log files appear in the bucket (allow several hours; delivery can lag up to 24 hours) and are JSON.
- [x] Record whether a WAF-blocked request appears as a 403 with result type Error, and add the answer to the spec's further notes.

## Blocked by

- Blocked by 02

## User stories addressed

Spec user stories: 48, 49

## Comments

- 2026-10-17: claimed. Seam: the stack template (code is tested; delivery of real logs is a human gate that takes hours). Confirming design choices with the owner before writing tests.
- 2026-10-17: template and golden done (prefix cloudfront/polls, Hive paths, default fields, no cookies). Deploy and delivery check still open.
- 2026-10-17: verified live. First log file arrived about 10 minutes after deploy (not hours): `cloudfront/polls/<distribution>.<date>-<hour>.<hash>.gz`, gzipped JSON lines. WAF-blocked POSTs appear as `sc-status` 403 with `x-edge-result-type` Error and `x-edge-detailed-result-type` Error. Requests the function rejects (400, 405) also read Error, so tell them apart by status and by the function log, not by result type.
- 2026-10-17: live check showed Hive paths do not apply without an explicit suffix path (first file landed flat). Added suffix `{yyyy}/{MM}/{dd}/{HH}`; expect keys `cloudfront/polls/year=.../month=.../day=.../hour=.../`. Verify after deploy.
- 2026-10-17: verified live after the suffix deploy: keys are now `cloudfront/polls/year=2026/month=10/day=17/hour=14/<dist>.<date>-<hour>.<hash>.gz`. All field values are JSON strings. `cs(Host)` is the cloudfront.net name; the real host is `x-host-header`.
