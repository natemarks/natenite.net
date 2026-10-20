# Map: web poll app at polls.natenite.net

## Destination

An **architecture decision**, with cited rationale, for hosting simple web polls at `polls.natenite.net/<poll-id>`: compute/hosting model (Lambda + API + static site vs App Runner), results storage, and routing/domain approach. Done when someone can plan the CDK stacks without reopening these choices.

## Notes

- Domain: AWS CDK (Python) repo `natenite.net`; prod account only, `us-east-1`. Existing stacks: Certificate (imported zone `natenite.net` + ACM cert for apex/www/`*.natenite.net`) and Site (S3 + CloudFront + WAF + OAC). Follow the repo's Input/Stack pattern and golden-test requirement.
- Poll shape (from the brief): each poll has its own route (`/poll1`); respondent gives an **optional email address** and answers the questions; results go to any easy storage (DynamoDB, JSON on S3, Athena, ...).
- Standing preferences: low cost at low traffic, minimal ops, avoid new always-on spend.
- Citations: research tickets must use the **aws-docs**, **aws-iac** and **aws-pricing** MCP servers and cite documentation URLs / pricing query parameters for every factual claim. Mark anything not verified as unverified.
- Earlier advice in this session (keep app code in a separate repo, infra here) is context, not a decision; the app-vs-infra repo split is revisited in the fog.
- Addenda to the research tickets: [research/07-docs-verification.md](research/07-docs-verification.md) closes many UNVERIFIED items and corrects the claim that a Lambda form POST through OAC always needs JavaScript (true for function URLs only). [research/06-verified-pricing.md](research/06-verified-pricing.md) re-verifies every price against the Price List API (us-east-1): none of the earlier prices was materially wrong, and the previously missing S3, CloudFront, NAT and endpoint rates are filled in. Free-tier allowances are not in the API and remain public-page-only.
- Tracker: local markdown. Tickets live in `tickets/`; a ticket is claimed by setting `claimed:` in its frontmatter, closed by setting `status: closed` and adding a `## Resolution` section.

## Decisions so far

<!-- one line per closed ticket: [title](tickets/file.md) — gist -->

- [Grill: observability and cost guardrails](tickets/08-grill-observability-guardrails.md) — no alerting; raw CloudFront JSON logs to an S3 bucket in the stack (365-day expiry) with Athena table, workgroup and saved queries; handler writes structured JSON lines to CloudWatch Logs (365-day retention) with saved Logs Insights queries; filtering and normalization deferred to a later phase
- [Grill: repo and deployment layout](tickets/07-grill-repo-deployment-layout.md) — everything in this repo, one CDK deploy; `polls/`, `lambda/submit/` (symlinked `polls`), `site/polls/`, `stack/polls.py` (`PollsInput`/`PollsStack`, `NateNiteProductionPollsStack`); asset hashes normalized in golden tests; fake-table handler tests plus a test validating every poll file; `make deploy-polls`/`diff-polls`; `PollsSetting` JSON for infrastructure numbers, `limits.py` for application limits; page logic tested with `node --test`
- [Grill: abuse limits](tickets/06-grill-abuse-limits.md) — WAF rate rule 20 POSTs per 5 min per IP on `/submit` (Block); Lambda reserved concurrency 2 (20 req/s, overruns monitorable via function URL metrics and `ConcurrentExecutions`); retry with backoff then friendly message; free text 500 chars, email 254, Lambda rejects bodies over 6 KB (shared ACL blocks over 8 KB)
- [Decide: architecture](tickets/04-decide-architecture.md) — Lambda Function URL (IAM) behind CloudFront OAC on a second distribution (reusing the wildcard cert and the existing WAF ACL plus a rate rule); Python Lambda; one on-demand DynamoDB table (`RESPONSE#`/`EMAIL#` records, retained, deletion-protected); shared `index.html` driven by poll JSON; definitions bundled into the Lambda. Compute choice recorded as [ADR 0001](../../../docs/adr/0001-lambda-function-url-with-cloudfront-oac.md); terms in the repo-root `CONTEXT.md`
- [Grill: poll definition and results access](tickets/03-grill-poll-definition.md) — email kept for manual use only (separate record, no TTL); owner-only script reads results; no results shown to respondents; JS acceptable; poll JSON in repo; single/multi/rating/free-text; ~100-5,000 responses per poll; soft dedupe with stored browser token; optional `closesAt`
- [Research: container platform alternatives](tickets/05-research-container-platforms.md) — ECS Express/Fargate need an always-on ALB (~$29-36/mo floor, lower-trust prices), Lightsail is a fixed $7/mo; Lambda is <$0.01/mo; containers only tip for sustained traffic, long-lived processes or shared ALB
- [Research: compute and hosting options](tickets/01-research-compute-hosting.md) — App Runner is closed to new customers and can't reuse the repo cert; HTTP API can't take WAF; Lambda Function URL + CloudFront OAC works but POST needs JS-computed payload hash; existing wildcard cert covers polls.natenite.net; Lambda options <$0.01/mo vs ~$2.6 App Runner
- [Research: results storage options](tickets/02-research-results-storage.md) — all options cost <$0.01/mo at ~1k responses; DynamoDB is the simplest (conditional-put dedupe, TTL, no extra infra); prices since verified (research/06)

## Frontier (open, unblocked)

(none)

## Blocked

(none)

## Not yet specified

(none: the way to the destination is clear)

## Out of scope

- Building or deploying anything. This map ends at the decision.
- Authoring the actual poll questions.
- **Observability data model:** after running the saved Athena and Logs Insights queries against real log data from a deployed stack, decide whether and how to filter and normalize events across sources into a WARN/ERROR-style stream, and whether handler events should move to S3. Out of scope because it needs data that only exists after the build; start it as a fresh effort then.
- **Privacy notice:** wording of the one-line notice on the form and whether any privacy regime applies to collecting an email (legal basis was not researched). Out of scope as launch content rather than architecture; keep it on the launch checklist.
