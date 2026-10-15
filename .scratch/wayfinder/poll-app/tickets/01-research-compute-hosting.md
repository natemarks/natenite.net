---
type: research
status: closed
claimed: research-agent-01
blocked_by: []
---

# Research: compute and hosting options

## Question

For simple polls at `polls.natenite.net/<poll-id>` (static form, one write per response, low traffic), what are the viable hosting models and how do they compare on cost at low traffic, ops burden, custom-domain and TLS handling, WAF/abuse protection, cold starts, and fit with the existing CDK stacks (CloudFront + WAF + wildcard ACM cert in `us-east-1`)?

Options to cover at minimum:
1. Static site (S3 + CloudFront) + API Gateway (HTTP API) + Lambda
2. Static site (S3 + CloudFront) + Lambda Function URL behind CloudFront (OAC for Lambda URLs)
3. Single Lambda serving HTML and API (Function URL or API Gateway)
4. AWS App Runner service (container)

Use the aws-docs, aws-iac and aws-pricing MCP servers. Cite documentation URLs and pricing query parameters. Pay attention to App Runner's current status and availability, its custom domain and certificate model, whether it supports WAF, and its idle/provisioned instance cost.

## Resolution

Findings: [research/01-compute-hosting.md](../research/01-compute-hosting.md).

- **App Runner is closed to new customers** (AWS doc: apprunner-availability-change). Whether this account is an existing customer is UNVERIFIED. AWS points to ECS Express Mode, which brings an always-on ALB. App Runner custom domains use their own ACM validation, so the repo's cert looks unreusable. Idle cost is about $2.6/month.
- **HTTP API cannot attach WAF** (REST API can), so WAF would have to sit on CloudFront.
- **Lambda Function URL behind CloudFront OAC works** with `AWS_IAM`, but POST bodies need an `x-amz-content-sha256` header, so the form needs JavaScript. CDK support for this is not checked.
- **The existing `*.natenite.net` us-east-1 cert covers `polls.natenite.net`** for CloudFront. Sharing the cert and web ACL across two distributions is UNVERIFIED.
- Cost at ~3,000 requests/month: Lambda options under $0.01 with the existing web ACL, about $7 with a dedicated ACL; App Runner about $2.6-3.
- Caveats: aws-pricing MCP failed (expired SSO), so prices are from public pages; CloudFront pay-as-you-go rates and App Runner build fees are UNVERIFIED.
- Left for the architecture decision: Lambda option 1 vs 2 vs 3, same vs second CloudFront distribution, whether the form must work without JavaScript.
