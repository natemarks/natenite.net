# Research 02: results storage options for poll responses

Ticket: tickets/02-research-results-storage.md. Date: 2026-10-15. Region assumed us-east-1.

Method and limits:
- Behaviour claims come from AWS docs read via the aws-docs MCP server (URLs cited).
- **The aws-pricing MCP failed** (`get_pricing` and `get_price_list_urls` for `AmazonDynamoDB`, us-east-1, both returned "Error when retrieving token from sso: Token has expired and refresh failed"). Prices below therefore come from the public aws.amazon.com pricing pages via WebFetch (a lower-trust fallback, with a small model summarising the page). Treat every price as **needs re-check with the pricing API after `aws sso login`**. Region caveats are noted per price.
- Anything not confirmed is marked UNVERIFIED.

## Comparison table

| | DynamoDB on-demand | S3 JSON objects + Athena | Firehose to S3 (+ Athena) |
|---|---|---|---|
| Write path from Lambda | One `PutItem` | One `PutObject` per response | `PutRecord` to a delivery stream (extra resource: stream + role) |
| Duplicate handling | Conditional put, atomic, per key | `If-None-Match` conditional write on key name | None built in; dedupe at query time |
| Owner reads results | Console / `Scan` / export to S3 then Athena | Athena SQL on the bucket (needs table DDL, workgroup, results bucket) | Athena SQL on the bucket |
| Retention / deletion of email | Native TTL; `DeleteItem` by key | Lifecycle expiration; delete the object by key | Lifecycle only; records are batched into shared objects, so delete-by-person means rewriting objects |
| Encryption at rest | Always on; AWS owned key default, KMS optional | SSE configurable (not read in this pass) | SSE-KMS supported on delivery |
| Cost at ~1,000 responses/month | Well under $0.01 | Well under $0.01 for queries; S3 request rate UNVERIFIED | Well under $0.01 for ingestion |
| Always-on spend | None (on-demand) | None | None, but extra moving parts |

## DynamoDB on-demand

- **Dedupe:** `PutItem` overwrites an existing item with the same primary key unless a condition expression is used. `attribute_not_exists(<key attr>)` lets the write proceed only if no item with that key exists, and a failed condition returns "The conditional request failed". On a composite key it is evaluated against the single item identified by both keys. Source: (https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html, section "Conditional put").
  - Implication: a dedupe key must be chosen. Dedupe by email is only possible if email is present; the email is optional. What to dedupe on (email, cookie/token, IP hash) is undecided.
- **TTL:** per-item expiry timestamp in a Number attribute, Unix epoch seconds. Items are deleted "typically within a few days after their expiration", not at the exact time. Expired-but-not-yet-deleted items still appear in reads, so use filter expressions. TTL deletes consume no write throughput. Source: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html
  - Implication: TTL is a retention backstop, not a precise or immediate deletion tool.
- **Export to S3:** requires point-in-time recovery (PITR) enabled; supports full and incremental exports in DynamoDB JSON or Ion; no RCU consumption; no SLA on completion time; charged by table size (full export) plus S3 storage and PUT. Output can be queried with Athena. Source: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/S3DataExport.HowItWorks.html
- **Encryption:** all user data is encrypted at rest; default key type is an AWS owned key at no additional charge; AWS managed or customer managed KMS keys are optional and incur KMS charges. Source: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/EncryptionAtRest.html
- **Pricing (fallback source, us-east-1 per the page's worked examples):** $0.625 per million write request units, $0.125 per million read request units, storage $0.25/GB-month with first 25 GB free (Standard class), PITR $0.20/GB-month, export $0.10/GB. Source: https://aws.amazon.com/dynamodb/pricing/on-demand/ (WebFetch). Re-check via pricing API (`AmazonDynamoDB`, us-east-1).
- **Owner read path:** console item explorer or a small `Scan`. For SQL, enable PITR and export to S3 for Athena. No built-in reporting UI.

## S3 JSON objects + Athena

- **Dedupe:** S3 conditional writes: `If-None-Match` on `PutObject` prevents overwrite when an object with the same key already exists; a bucket policy can enforce the header. Source: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html and https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html (search results only; page bodies not read in full, so exact failure semantics UNVERIFIED). The key would have to be derived from the dedupe identity (for example a hash).
- **Athena over JSON:** the OpenX JSON SerDe requires each JSON record on one line; pretty-printed or whole-file JSON is not read correctly (Ion SerDe is the alternative). One object per response containing a single-line JSON record works. Source: https://docs.aws.amazon.com/athena/latest/ug/querying-JSON.html
- **Many tiny objects:** Athena partitioning and partition projection guidance is at https://docs.aws.amazon.com/athena/latest/ug/partitions.html (not read in full). Small-file performance impact at 1,000/month is not expected to matter; UNVERIFIED.
- **Retention:** S3 Lifecycle Expiration permanently deletes objects after N days. Source: https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html (search result only). Deletion for one person means `DeleteObject` on a known key; finding the key by email requires an Athena query or a key derived from the email (which then makes the key itself personal data).
- **Pricing (fallback source):** Athena $5 per TB scanned (page does not name a region; UNVERIFIED for us-east-1), https://aws.amazon.com/athena/pricing/. S3 GET $0.0004 per 1,000 (stated in a us-east-1 example), https://aws.amazon.com/s3/pricing/. **S3 PUT and storage rates were not obtainable: UNVERIFIED.**
- **Extra infrastructure:** Glue/Athena table definition, workgroup, query results bucket, plus a bucket policy. This is more CDK than DynamoDB.

## Firehose to S3 (extra option)

- Firehose buffers records and delivers batched objects to S3; optional newline delimiter ("If you plan to use Athena to query S3 objects with aggregated records, enable this option"), GZIP/Snappy/Zip compression, dynamic partitioning, SSE-KMS. Source: https://docs.aws.amazon.com/firehose/latest/dev/create-destination.html
- Delivery is delayed by the buffering hints, so results are not immediately visible. Buffering interval defaults not read: UNVERIFIED.
- Pricing (fallback source, region not stated, UNVERIFIED for us-east-1): Direct PUT $0.029/GB, billed in 5 KB increments; dynamic partitioning $0.020/GB plus $0.005 per 1,000 objects. https://aws.amazon.com/firehose/pricing/
- No native dedupe, and shared batched objects make per-person deletion hard. Designed for streaming volumes far above this use case; included for completeness.

## Rough monthly cost at ~1,000 responses/month

Assumption: each response is under 1 KB (answers plus optional email). Arithmetic is mine, using the fallback prices above.

- **DynamoDB:** 1,000 writes x 1 WRU = 1,000 WRU = 0.001 million x $0.625 = about $0.0006. Reads for a few `Scan`s: negligible. Storage: about 1 MB, inside the 25 GB free tier. PITR (needed only for export): 0.001 GB x $0.20 = under $0.001. Total: under $0.01.
- **S3 + Athena:** Athena scans of about 1 MB of data; even the 10 MB federated-query minimum (not confirmed for S3 queries) would be 10 MB x $5/TB = about $0.00005 per query. S3 PUT cost for 1,000 objects: rate UNVERIFIED. Total: expected well under $0.01, with the PUT rate unconfirmed.
- **Firehose:** 1,000 records x 5 KB minimum = 5 MB = 0.005 GB x $0.029 = about $0.00015, plus S3 and Athena as above.
- All three are effectively free at this volume. The meaningful differences are build complexity, dedupe, deletion, and read ergonomics, not cost.

## Optional email as personal data

- Email is personal data under common privacy regimes; whether this site must comply with a specific regime is not researched (out of scope for the docs searched here, UNVERIFIED).
- Encryption: DynamoDB and S3 both encrypt at rest by default (DynamoDB confirmed above; S3 default not read in this pass, UNVERIFIED). A customer managed KMS key adds access control and an audit trail, and adds KMS charges (DynamoDB doc above).
- Retention: DynamoDB TTL (days-level imprecision) or S3 lifecycle (day granularity). If the email is only needed briefly, TTL on the whole item deletes answers too, so splitting email into a separate item or table lets answers outlive the email. That is a modelling choice, not decided here.
- Deletion on request: DynamoDB by key is simple if the email (or a hash) is the key or in an index; S3 needs a known key; Firehose batching makes it hard.
- Exports and Athena results copy personal data into additional S3 locations, which also need retention rules. PITR backups hold deleted data for the PITR window (window length not read here: UNVERIFIED).
- Whether the email is used for follow-up (SES) is an open map item and would change the retention answer.

## What this leaves undecided

1. Dedupe identity: email (optional), a browser token, an IP hash, or none, and what failure the respondent sees on duplicate.
2. Whether email is stored with the answers or separately, and its retention period and deletion process.
3. How the owner reads results: console and ad-hoc scans, a small results page/API, or Athena SQL (depends on ticket 03).
4. Whether PITR (and export to S3) is wanted at all, given its extra cost and its effect on deletion semantics.
5. KMS key choice (AWS owned default vs customer managed) and whether the table should be retained on stack deletion.
6. Real prices from the pricing API (S3 PUT and storage, Athena and Firehose region confirmation) once SSO is refreshed.
7. Legal basis and notice text for collecting email (not researched).
