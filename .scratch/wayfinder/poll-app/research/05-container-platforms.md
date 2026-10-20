# Research 05: container platform alternatives vs the Lambda family

Ticket: `tickets/05-research-container-platforms.md`. Researched 2026-10-15 by research-agent-05. Evidence, not a decision.
Lambda cost, cert and WAF findings are reused from [01-compute-hosting.md](01-compute-hosting.md) (cited as "R01"); not redone here.

## Method and caveats

- Docs: aws-docs and aws-iac MCP servers (search/read). CDK API facts come from the aws-iac CDK doc search (constructs.dev, aws-cdk-lib 2.273.0).
- **aws-pricing MCP failed again** on the one try (`get_pricing`, service `AWSELB`, us-east-1, productFamily "Load Balancer-Application"): "Error when retrieving token from sso: Token has expired and refresh failed". All prices below are **LOWER-TRUST**: read via page-summarising fetch of public aws.amazon.com pages and **need a re-check via the Price List API after `aws-login`**. Sources per price are given inline.
- Monthly figures assume 730 hours/month. Arithmetic is mine; inputs are cited.

## 1. What ECS Express Mode provisions

- Required inputs: container image, task execution role, infrastructure role. It orchestrates "a Fargate-based ECS service with a unique accessible URL, load balancer with SSL/TLS, auto scaling policies, monitoring, and networking components" (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html).
- Resource list (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html): ECS default cluster (Fargate capacity provider) if absent; task definition; service with canary deployment and auto scaling; **Application Load Balancer with HTTPS listener, listener rules, target groups**; security groups; service-linked roles; Application Auto Scaling target + target-tracking policy; log group; metric alarm for faulty deployments; **ACM certificate**.
- Defaults: 1 vCPU / 2 GB, x86_64, container port 80, min tasks 1, max 20, CPU target 60% (same page). Scaling metrics: CPU, memory, or request count per target (same page).
- Networking: with no subnets given, uses default-VPC public subnets (needs >=2 public subnets in >=2 AZs). Custom public subnets give an **internet-facing ALB** and `assignPublicIP` on tasks; private subnets give an **internal ALB** and no task public IP, and you must supply NAT if tasks need internet (same page).
- Pricing: "no additional charge" for Express Mode; you pay for Fargate, ALB, CloudWatch logs/metrics, data transfer (express-service-overview page above).
- Cost sharing: up to 25 Express services in one VPC share one ALB; Express deprovisions unused ALBs (express-service-work page, "Resource sharing and cost optimization").
- Default URL format `servicename.ecs.region.on.aws` (search result snippet of https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html; page body not read).

### Scale to zero / avoid the ALB

- **ALB cannot be avoided in Express Mode.** It is part of the provisioned set, and "load balancer configurations can not be updated on Express Mode services" (express-service-work page). The only sharing lever is spreading the ALB cost across up to 25 services.
- **Scale to zero is not documented for Express Mode.** `MinTaskCount` is an optional integer; the docs read do not state its minimum, so whether 0 is accepted is **UNVERIFIED** (https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-expressgatewayservice-expressgatewayscalingtarget.html). Express default is min 1.
- General ECS service auto scaling does allow it: "If you want your task count to scale to zero when there's no work to be done, set a minimum capacity of 0 ... when actual capacity is 0 and the metric indicates that there is workload demand, Service Auto Scaling waits for one data point to be sent before scaling out" (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-auto-scaling.html, Considerations). Whether an ALB request can wake a zero-task service (request-count metric with no registered targets) is **UNVERIFIED** and not described; do not assume request-driven cold start like Lambda. Even if tasks hit zero, the ALB hourly charge continues.

## 2. Cost components (always-on), us-east-1 (LOWER-TRUST, re-check)

| Item | Price | Source |
|---|---|---|
| ALB hourly | $0.0225 per ALB-hour (partial hour billed as full) | https://aws.amazon.com/elasticloadbalancing/pricing/ (worked examples, us-east-1) |
| ALB LCU | $0.008 per LCU-hour; 1 LCU = 25 new conn/s, 3,000 active conn/min, 1 GB/h, 1,000 rule evals/s; billed on highest dimension | same page |
| Fargate Linux x86 | $0.000011244 /vCPU-s, $0.000001235 /GB-s (= $0.04048 /vCPU-h, $0.004446 /GB-h); 1-minute minimum; 20 GB ephemeral included | https://aws.amazon.com/fargate/pricing/ |
| Fargate Linux ARM | $0.0000089944 /vCPU-s, $0.0000009889 /GB-s | same page |
| Public IPv4 | $0.005 per address-hour, in-use and idle | https://aws.amazon.com/vpc/pricing/ |
| NAT gateway | Only a us-east-2 (Ohio) example was shown: $0.045/h and $0.045/GB. **UNVERIFIED for us-east-1** | same page |
| Smallest Fargate task | 0.25 vCPU with 512 MiB (valid combination) | https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html |

Derived monthly costs (730 h):

- ALB hourly: $16.43. LCU at about 3,000 requests/month: far below 1 LCU; billed LCU fraction unverified, upper bound for 1 LCU all month is $5.84. So treat ALB as about $16.4 to $22.3.
- Internet-facing ALB public IPv4: the Express doc requires >=2 AZs, so at least 2 addresses = about $7.30/month (assumes one address per AZ, not confirmed in the page read). An internal ALB uses private IPs (express-service-work page), so no public IPv4 charge on the ALB (inference).
- Fargate 0.25 vCPU / 0.5 GB, 1 task always on: x86 about $9.01/month; ARM about $7.21/month. Express default 1 vCPU / 2 GB x86: about $36.04/month.
- Public IPv4 on the task (needed in a public subnet to pull images without NAT or endpoints): about $3.65/month per task.
- NAT or ECR/other VPC endpoints for private-subnet tasks: NAT would be about $32.85/month from the Ohio rate (UNVERIFIED), which alone exceeds the rest. Interface-endpoint pricing not researched (**UNVERIFIED**). The ECS docs say Fargate tasks in private subnets need ECR endpoints or NAT to pull images (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html and https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html, search-result titles only; detail not read).
- Public-subnet shape (no NAT): ALB $16.43 + (ALB IPv4 $7.30 if internet-facing) + task $9.01 + task IPv4 $3.65 = about **$29 (internal ALB) to $36 (internet-facing)** before LCU, logs, WAF.
- ECR storage and CloudWatch Logs: not priced (**UNVERIFIED**, small).

## 3. Can ECS sit behind CloudFront and use the existing wildcard cert?

- **Yes, via VPC origins.** CloudFront can deliver from ALBs, NLBs and EC2 in private subnets (https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html). Requirements: VPC with an internet gateway; a private subnet with a free IPv4 for a CloudFront-managed ENI ("no additional cost for them"); ALB must be Active and carry a security group allowing the CloudFront prefix list `com.amazonaws.global.cloudfront.origin-facing` or the service-managed SG; creation can take up to 15 minutes. Not supported: gRPC, Lambda@Edge origin request/response triggers, NACL inbound evaluation. A VPC origin has no listed extra charge in the pages read (sharing page says no extra charge for sharing; VPC origin base charge **UNVERIFIED**).
- CDK has an L2 for it: `aws_cloudfront_origins.VpcOrigin` with `withApplicationLoadBalancer(...)` (aws-cdk-lib 2.273.0, https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/VpcOrigin?lang=typescript&submodule=aws_cloudfront_origins). The older `LoadBalancerV2Origin` needs an internet-facing ALB ("'internetFacing' must be 'true' for CloudFront to access the load balancer", https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/LoadBalancerV2Origin?lang=go&submodule=aws_cloudfront_origins).
- Interaction with Express Mode: Express picks internal vs internet-facing ALB from the subnets you pass (express-service-work page), so an Express service with private subnets yields an internal ALB suitable as a VPC origin. Whether Express-created ALBs/tags tolerate being referenced by an external CloudFront VPC origin was **not found in docs (UNVERIFIED)**.
- **Viewer cert (CloudFront side):** the existing us-east-1 `*.natenite.net` cert covers `polls.natenite.net` (R01 headline finding 4). Nothing new for the viewer side.
- **Origin-side TLS:** CloudFront to ALB over HTTPS needs a cert on the ALB listener for the origin hostname. Express creates its own ACM certificate for its default `*.ecs.<region>.on.aws` URL (resource list above); using the existing wildcard on the ALB means attaching it to the listener, which the docs describe as a manual console procedure ("Add certificate" on the listener, plus host-header rule) in https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-advanced-customization.html. HTTP-only CloudFront to ALB origin is possible in principle but not verified here (**UNVERIFIED**).
- **No CloudFront: custom domain direct on the Express ALB.** Documented as a manual procedure: change the listener rule host-header condition to add your domain, add the ACM certificate to the HTTPS listener, create a Route 53 alias to the ALB (same page). Existing wildcard cert (us-east-1) works with an ALB in us-east-1 because ALB certs are regional (regional match is standard but this exact statement was not read; **UNVERIFIED**). Express updates may conflict with hand edits: "Express Mode will not overwrite changes unless requested as part of an Express Mode update" and the user is responsible for conflicts (same page).

## 4. WAF

- Regional web ACLs attach to ALBs (`AWS::WAFRegional::WebACLAssociation` ResourceArn is an ALB; https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-wafregional-webaclassociation.html; the WAFv2 CLI doc covers `associate-web-acl` for regional resources, https://docs.aws.amazon.com/cli/latest/userguide/cli_wafv2_code_examples.html). The repo's ACL is CLOUDFRONT scope and is for CloudFront only (R01 section 4; https://docs.aws.amazon.com/waf/latest/APIReference/API_AssociateWebACL.html).
- Two routes, then: (a) put the ALB behind CloudFront and attach the existing CloudFront-scope ACL on the distribution (no new ACL; but the ALB then must reject non-CloudFront traffic, which the VPC origin + internal ALB does by construction); (b) a new regional ACL on the ALB (new ACL fee, about $5 + $1/rule per R01 pricing, so about $7 with two managed groups).
- Express Mode creates no WAF resource (not in the resource list). Whether Express tolerates an external WAF association: **UNVERIFIED** (direct ALB association is a standard ELB-side action; not confirmed for Express-managed ALBs).

## 5. Lightsail Containers

- Model: a container service has **scale** (1 to 20 nodes) and **power** (Nano to Xlarge); monthly price = power price x nodes; "You are charged for your container service whether it's enabled or disabled, and whether it has a deployment or not. You must delete your container service to stop being charged." Each service includes 500 GB/month transfer; overage starts at $0.09/GB (https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html).
- Prices (LOWER-TRUST, https://aws.amazon.com/lightsail/pricing/): Nano $7 (0.25 shared vCPU, 512 MB), Micro $10 (0.25, 1 GB), Small $15 (0.5, 1 GB), Medium $40 (1, 2 GB), Large $80, Xlarge $160. No container free trial stated on the page.
- **No scale to zero and no pay-per-request**: fixed monthly price; the cheapest viable always-on is about **$7/month** (Nano).
- Limits: one public-endpoint container per service, up to 10 containers per deployment, one active deployment, HTTPS-only public endpoint (no TCP/UDP), 50 saved deployment versions, Linux images only (same container-services page). Images come from a public registry or are pushed from a local machine to the service (no ECR needed in the docs' list of sources).
- Custom domain/TLS: needs a **Lightsail-issued certificate** validated by CNAME, "issued by ACM" but created in Lightsail, then attached to the service; up to **4 custom domains per service**; a domain cannot be on more than one service (https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-tls-ssl-certificates-in-lightsail-https.html and .../amazon-lightsail-enabling-container-services-custom-domains.html). The docs read describe no way to attach the existing CDK-managed ACM cert; reuse of `*.natenite.net` directly is **not supported as far as documented (UNVERIFIED that it is impossible)**. Apex/subdomain routing to a service is documented for Lightsail DNS zones; a Route 53 alias page exists (title only read).
- WAF: not found in what was read; whether a Lightsail endpoint can take a WAF ACL is **UNVERIFIED**. CloudFront in front: possible in principle using the default `*.cs.amazonlightsail.com` HTTPS domain as a custom origin, with the existing wildcard cert on CloudFront and the repo ACL on the distribution (**UNVERIFIED**, not documented in the pages read; also Lightsail has its own CDN "distributions" feature, not researched).
- CDK: **L1 only**, `aws_lightsail.CfnContainer` (`power`, `scale`, `service_name`, ...) (https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/CfnContainer?lang=python&submodule=aws_lightsail). No L2 found. Whether CloudFormation supports certificate/domain attachment to the service is not checked (**UNVERIFIED**; the console/API flow is manual per above).
- Ops: image push via `lightsailctl` from a local machine; no ECR required; no VPC to manage. Patching the image is still on you.

## 6. Other AWS options surfaced

- **Elastic Beanstalk**: no additional charge, you pay for underlying resources (https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/Welcome.html); the web-server environment includes Auto Scaling, load balancer and security group (relationship text in the same search). The Docker AL1 platform branch is retired (https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/docker-platform.html). Single-instance (no load balancer) environments exist in Beanstalk but I did **not verify** that or the EC2 cost here, so Beanstalk is **UNVERIFIED** beyond "ALB or EC2 always-on". Not a better fit for the repo's CDK pattern; not researched further.
- **ECS on Fargate behind an ALB with plain CDK** (option 2 in the ticket): `aws_ecs_patterns.ApplicationLoadBalancedFargateService` is an L3 pattern with `cluster`, `cpu`, `memoryLimitMiB`, `desiredCount`, `taskImageOptions`, and `service.autoScaleTaskCount(min_capacity, max_capacity)` (https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/ApplicationLoadBalancedFargateService?lang=typescript&submodule=aws_ecs_patterns). Same ALB/Fargate/IPv4 cost structure as Express Mode, but with VPC, cluster, subnet, security group and cert wiring explicit and golden-testable. The pattern also exposes domain and certificate props (the multi-target-group example shows `DomainName`); exact prop names for ALB certificate/zone were not read (**UNVERIFIED**).
- **ECS Express in CDK**: only L1 found: `aws_ecs.CfnExpressGatewayService` (props `infrastructureRoleArn`, `cpu`, `memory`, `healthCheckPath`, `networkConfiguration`, `primaryContainer`, scaling target; https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/CfnExpressGatewayService?lang=typescript&submodule=aws_ecs). The doc search found **no L2 `ExpressGatewayService`**; absence in the doc index is not proof (**UNVERIFIED**). CloudFormation resource type is `AWS::ECS::ExpressGatewayService` (https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-expressgatewayservice-expressgatewayscalingtarget.html). There is a CloudFormation operations page for Express (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-express-mode.html, "Resource readiness considerations"); not read in full.

## 7. CDK and repo fit

- Repo pattern (read from `stack/site.py`, `stack/certificate.py`): Input dataclass + Stack class, imported hosted zone, cert with apex/www/`*.natenite.net`, one CloudFront distribution with alias A-records, CLOUDFRONT-scope WAF ACL, golden tests per environment.
- Express (L1) hides resources behind the service: the ALB, cluster, SGs, ACM cert, scaling target are created by ECS, not in the CloudFormation template, so **golden tests would not cover them** and extra wiring (VPC origin, WAF, custom host rule) relies on hand edits or custom resources. Inference from the docs' "Express Mode APIs manage resources on your behalf" model.
- Plain ECS pattern and Lightsail L1 both put every resource in the template (golden-testable), but ECS adds VPC, ECR (or registry), cluster, ALB, task, scaling, and an image build/push pipeline; Lightsail adds one resource but manual cert/domain steps.
- Image pipeline needs a build step and registry in all container options. Lambda zip or inline needs none (R01).

## 8. Head-to-head at ~1,000 responses/month (about 3,000 requests)

Lambda figures from R01 (cost section): Function URL + OAC and HTTP API + Lambda both come to under $0.01/month with the existing ACL shared; about $7 if a dedicated ACL is added.

| Dimension | Lambda Function URL + CloudFront OAC | HTTP API + Lambda (behind CloudFront) | ECS Express Mode | Plain ECS Fargate + ALB (+CloudFront VPC origin optional) | Lightsail Containers (Nano) |
|---|---|---|---|---|---|
| Approx monthly (LOWER-TRUST) | < $0.01 (R01) | < $0.01 (R01) | about $29 to $36 at 0.25/0.5 task; about $56 to $63 at the 1 vCPU/2 GB default (ALB $16.4 + task + IPv4s, before LCU/logs/WAF) | about $29 to $36 at 0.25/0.5 task, same components | $7 (fixed) |
| Idle cost | about $0 | about $0 | ALB + 1 task | ALB + 1 task (min 0 possible in ECS autoscaling but ALB still billed) | $7 whether used or not |
| Scale to zero | Native | Native | Not documented; ALB cannot be removed | Task count to 0 possible via Application Auto Scaling; request-driven wake UNVERIFIED | No |
| Public IPv4 charge | none for you (R01) | none | ALB (2+ if internet-facing) + task | Same; internal ALB avoids ALB IPv4 | Not itemised |
| Existing wildcard cert | Yes on CloudFront (R01) | Yes on CloudFront (R01) | On CloudFront yes; on ALB manual cert attach | Yes on CloudFront; CDK can attach ACM cert to ALB | Not documented (own Lightsail cert); via CloudFront in front UNVERIFIED |
| WAF | Existing CloudFront ACL (R01) | CloudFront ACL only; HTTP API cannot take WAF (R01) | Via CloudFront ACL, or new regional ACL (about $7) | Same | Unverified |
| Lock to CloudFront | OAC + AWS_IAM (R01) | Origin header secret (R01) | VPC origin + internal ALB | VPC origin + internal ALB | Not documented |
| Plain HTML form POST | Needs JS-computed payload hash through OAC (R01) | Yes | Yes | Yes | Yes |
| CDK support | L2 for Lambda; OAC exact support UNVERIFIED (R01) | L2s | L1 only (CfnExpressGatewayService) | L3 pattern + L2 VpcOrigin | L1 only (CfnContainer) |
| Image build/registry/patching | None | None | Yes | Yes | Yes (push to service) |
| Golden-test fit | Good | Good | Poor (managed resources outside template) | Good | Good for the service, domain/cert manual |
| Ops burden | Lowest | Low | Medium | Medium-high | Medium-low |

Contrast notes:
- Containers trade pay-per-request for a floor of $7 (Lightsail) to about $29-$36 (ECS) per month, about three orders of magnitude over Lambda at this traffic. This conflicts directly with the map's "avoid new always-on spend" preference.
- Containers remove Lambda's constraints: no OAC POST-hash workaround (as the ALB/VPC-origin route has no payload-hash requirement in the docs read; HTTP API route already avoids it), long-lived process, any framework, in-memory state, WebSockets (ALB supports WebSockets per search relationship text).
- App Runner is closed to new customers (R01), so no cheaper managed-container middle ground remains in the docs read except Lightsail.

## 9. What workloads would tip toward containers

(Reasoned from the sources above, not stated by AWS.)
- Sustained traffic where a task is busy a large share of the time, so Lambda's per-request/GB-s billing exceeds the ~$30/month floor (Lambda per-unit prices in R01).
- Need for long-lived processes, WebSocket/streaming, large dependencies or local state that do not fit Lambda packaging or its runtime model.
- Several apps sharing one ALB (Express shares one ALB across up to 25 services in a VPC) to amortise the fixed ~$16/month.
- A team that already ships container images and wants identical local and cloud runtimes.
- Not tipping: simple form POST, optional email, about 1,000 responses/month.

## 10. What this leaves undecided

- Exact prices: re-run Price List API (ALB LCU minimum billing, NAT us-east-1, interface endpoints, Fargate, VPC origin, CloudFront) after `aws-login`.
- Whether Express `MinTaskCount` accepts 0 and whether an ALB request can wake a zero-task service.
- Whether Express-managed ALBs can safely take an external VPC origin, WAF association or extra listener cert under CloudFormation without drift.
- Whether Lightsail can use the existing ACM cert, take a WAF ACL, or sit behind CloudFront (documented route is a Lightsail-issued cert and its own domain assignment).
- Whether a container option is wanted at all given the ~3 order-of-magnitude cost gap; this ticket supplies no preference for or against.
- Express L2 construct existence (only L1 found); CDK/CloudFormation coverage for Lightsail cert/domain.
- Whether the account can still use App Runner (R01 open item), only relevant if a managed-container alternative is wanted.
- Elastic Beanstalk single-instance cost and fit (not verified).
- Image build/registry and deploy pipeline location (ties to repo split in the map's fog).

## Sources index

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-advanced-customization.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html (snippet)
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-auto-scaling.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/networking-outbound.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-expressgatewayservice-expressgatewayscalingtarget.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-wafregional-webaclassociation.html
- https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html
- https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-enabling-container-services-custom-domains.html
- https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-tls-ssl-certificates-in-lightsail-https.html
- https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/Welcome.html
- constructs.dev aws-cdk-lib 2.273.0: CfnExpressGatewayService, VpcOrigin, LoadBalancerV2Origin, ApplicationLoadBalancedFargateService, CfnContainer (URLs inline)
- Prices (LOWER-TRUST page fetches): https://aws.amazon.com/elasticloadbalancing/pricing/ , https://aws.amazon.com/fargate/pricing/ , https://aws.amazon.com/vpc/pricing/ , https://aws.amazon.com/lightsail/pricing/
- Pricing MCP attempt: `get_pricing` AWSELB / us-east-1 / productFamily=Load Balancer-Application, failed with expired SSO token.
