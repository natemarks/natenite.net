---
type: research
status: closed
claimed: research-agent-02
blocked_by: []
---

# Research: results storage options

## Question

Where should poll responses (answers plus an optional email address) be stored? Compare DynamoDB (on-demand), S3 JSON objects (one per response, or batched) queried with Athena, and any other easy option you find (for example Kinesis Data Firehose to S3). Cover cost at low traffic, write path complexity from Lambda, how the poll owner reads or exports results, duplicate-submission handling, and handling of the optional email as personal data (encryption, retention/TTL, deletion).

Use the aws-docs, aws-iac and aws-pricing MCP servers. Cite documentation URLs and pricing query parameters; mark anything unverified.

## Resolution

Findings: [research/02-results-storage.md](../research/02-results-storage.md).

- All three options (DynamoDB on-demand, S3 JSON + Athena, Firehose to S3) cost well under $0.01/month at ~1,000 responses. Cost does not discriminate; build complexity, dedupe, deletion and read ergonomics do.
- DynamoDB: atomic dedupe via conditional put, native TTL (days-level imprecision), no extra infrastructure. S3 + Athena needs table, workgroup and results bucket. Firehose has no native dedupe and makes per-person deletion hard.
- Caveats: the aws-pricing MCP failed (expired SSO token), so all prices come from public pricing pages and need a re-check; S3 PUT/storage rates and some S3 page details are UNVERIFIED; legal basis for collecting email was not researched.
- Left for the architecture decision: dedupe identity, email stored separately or not, retention, how the owner reads results, whether PITR is wanted.
