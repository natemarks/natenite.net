---
type: grilling
status: closed
claimed: nate (architecture session)
blocked_by: []
---

# Decide: architecture

## Question

Given the research on compute/hosting and storage and the poll definition decisions, choose the architecture for `polls.natenite.net`: Lambda/API + static site vs App Runner, the storage choice, and the routing/domain approach. Record the rationale with the citations from tickets 01 and 02. Graduate any fog in the map that this decision makes specifiable.

## Resolution

Confirmed by the human. Decisions (compute choice also recorded as [ADR 0001](../../../../docs/adr/0001-lambda-function-url-with-cloudfront-oac.md); terms in the repo-root `CONTEXT.md`):

1. **Compute:** Lambda Function URL (`AuthType: AWS_IAM`) behind CloudFront with OAC (origin type `lambda`, sigv4, always). Browser `fetch` sends `x-amz-content-sha256` (SHA-256 of the body). CDK L2 `FunctionUrlOrigin.with_origin_access_control` adds both Lambda permissions. Rejected: Web Function (Node.js only, resource policy has no IaC resource), HTTP API (extra $1/M, shared-secret header, WAF cannot attach to HTTP API). Cites: research/01, research/07 section 1.
2. **Routing:** second CloudFront distribution in a new stack for `polls.natenite.net` (own S3 origin for poll pages and JSON, Lambda Function URL origin for the submit path), reusing the existing `*.natenite.net` ACM cert and a Route 53 alias record. Rejected: third alternate name on the existing distribution (needs a Host-routing CloudFront Function, rewrites the main site's function, and touches the index-based OAC override in `SiteStack`). Cites: research/07 section 2.
3. **WAF:** share the existing CloudFront-scope web ACL. `SiteStack` exports it; the polls distribution attaches it. Add a per-IP rate-based rule scoped (scope-down) to the `polls.natenite.net` Host (about +$1/month). Requires editing `SiteStack` and its golden test; polls stack depends on Site stack. Rejected: dedicated ACL (~$8/month), no WAF (no per-IP limiting). Cites: research/06 (ACL $5, rule $1), research/07 section 7b (rate rule minimum 10, windows 60-600 s, not precise).
4. **Storage layout:** one DynamoDB on-demand table, partition key = poll ID, sort key = record type + ID. `RESPONSE#<responseId>` holds answers by question ID, hashed browser token, submitted-at, poll definition version. `EMAIL#<responseId>` holds the address (separate record per tickets/03 decision 9). Response IDs are time-sortable (ULID). One query returns a poll's data; email joins by response ID. Delete-by-address is a filtered scan (no index at this volume). Rejected: two tables. Point-in-time recovery off (tickets/03). Cites: research/02, research/07 section 4.
5. **Lambda runtime:** Python (matches repo language, pytest, tooling; handler is a small validate-and-write function). Gives up the Node-only Web Function path, already ruled out by the IaC gap.
6. **Page rendering:** one shared `index.html`. A small viewer-request CloudFront Function rewrites `/<poll-id>` (not the submit path, not files with extensions) to `/index.html`; the page script reads the poll ID from the URL, fetches the poll definition JSON from the same S3 origin, and builds the form. Unknown poll ID shows a "poll not found" message. Rejected: generated page per poll (needs a generator and build).
7. **Definitions for validation:** bundled into the Lambda package at deploy time from the same `polls/` directory that feeds the S3 upload; one CDK deploy, no runtime S3 read, no drift between form and server rules. Each new poll redeploys the function (accepted in tickets/03 decision 5).
8. **Data protection:** responses table has `RemovalPolicy.RETAIN` and DynamoDB deletion protection enabled (unlike the site bucket's DESTROY). Stack termination protection stays off, matching the rest of the repo.
