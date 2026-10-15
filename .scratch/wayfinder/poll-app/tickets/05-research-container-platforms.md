---
type: research
status: closed
claimed: research-agent-05
blocked_by: []
---

# Research: container platform alternatives vs the Lambda option

## Question

Now that App Runner is closed to new customers (see [Research: compute and hosting options](01-research-compute-hosting.md)), what are the viable container or server-based alternatives for hosting polls at `polls.natenite.net/<poll-id>`, and how do they compare and contrast with the Lambda family (S3 + CloudFront + Lambda Function URL or HTTP API)?

Options to cover at minimum:
1. ECS Express Mode (AWS's recommended App Runner replacement)
2. ECS on Fargate behind an ALB, built with plain CDK
3. Lightsail Containers (fixed-price option)
4. Any other AWS option the docs surface for small web apps (for example Elastic Beanstalk, or ECS behind CloudFront with a VPC origin)

Compare on: always-on cost vs Lambda at ~1,000 responses/month (ALB, Fargate, NAT/endpoints, public IPv4 charges), custom domain and reuse of the existing `*.natenite.net` us-east-1 ACM cert and hosted zone, WAF attachment, scale-to-zero behaviour, ops burden (image build, ECR, patching, deploys), CDK support and fit with this repo's stack pattern, and what workloads would tip the balance toward containers. Use the aws-docs, aws-iac and aws-pricing MCP servers. Cite documentation URLs and pricing query parameters; mark anything unverified.

## Resolution

Findings: [research/05-container-platforms.md](../research/05-container-platforms.md).

- **ECS Express Mode** always provisions an ALB (not removable), a Fargate service and its own ACM cert. Scale to zero is not documented. Cost floor about $29-36/month at the smallest task (ALB $16.4 + task + public IPv4s), about $56-63 at the 1 vCPU / 2 GB default. Lower-trust prices.
- **Plain ECS Fargate + ALB** has the same cost structure but is golden-testable (L3 `ApplicationLoadBalancedFargateService`, L2 `VpcOrigin` for CloudFront).
- **Lightsail Containers** is a fixed $7/month (Nano), no scale to zero, own certificate (existing ACM cert not documented as usable), WAF unverified, L1 CDK only.
- Behind CloudFront via a VPC origin, the existing wildcard cert covers the viewer side and the existing CloudFront WAF ACL can be reused.
- Versus Lambda (under $0.01/month): about three orders of magnitude more at this traffic, conflicting with "avoid new always-on spend". Containers win only for sustained traffic, long-lived processes or WebSockets, or several apps sharing one ALB; none apply to simple polls.
- Caveats: pricing MCP failed (see map notes), so all prices need a Price List API re-check; Express MinTaskCount 0, Express ALB tolerance for external VPC origin/WAF, and Lightsail cert/WAF reuse are UNVERIFIED.
