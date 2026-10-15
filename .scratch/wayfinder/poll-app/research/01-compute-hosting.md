# Research 01: compute and hosting options for polls.natenite.net

Ticket: `tickets/01-research-compute-hosting.md`. Researched 2026-10-15 by research-agent-01.
This is evidence, not a decision.

## Method and caveats

- Docs: aws-docs MCP (search/read). Prices: the **aws-pricing MCP failed** ("Token has expired and refresh failed", SSO). No Price List API queries succeeded. All prices below were read from the public pricing pages at aws.amazon.com via a page-summarising fetch. The summariser sometimes could not find rate tables, so each price carries its source and gaps are marked UNVERIFIED. Re-run via the Pricing API after `aws-login` if exact figures matter.
- Existing repo setup was read from `stack/site.py` and `stack/certificate.py`: ACM cert for apex, `www.` and `*.natenite.net` (imported hosted zone via `from_lookup`), one CloudFront distribution (alt names apex + www only, PRICE_CLASS_100, S3 OAC), a CLOUDFRONT-scope WAF web ACL with `AWSManagedRulesCommonRuleSet` and `AWSManagedRulesKnownBadInputsRuleSet`.

## Headline findings

1. **App Runner is closed to new customers.** "AWS App Runner is no longer open to new customers. Existing customers can continue to use the service as normal, including creating new resources and services... we do not plan to introduce new features." AWS recommends ECS Express Mode instead (which provisions an ALB, Fargate service, etc.). Source: https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html . The release notes cite April 30, 2026 as the closing date (search-result snippet of https://docs.aws.amazon.com/apprunner/latest/relnotes/relnotes-2024.html). Whether this AWS account counts as an "existing customer" is **UNVERIFIED** (not checkable from docs).
2. **API Gateway HTTP APIs cannot attach AWS WAF**; REST APIs can. Source: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html (Security table: AWS WAF, REST API Yes, HTTP API No). So with an HTTP API, WAF must sit in front on CloudFront.
3. **Lambda Function URL + CloudFront OAC works**, with a catch for POST. The function URL must use `AuthType: AWS_IAM`; the OAC has origin type `lambda`, sigv4, signing behavior `always`; CloudFront needs a resource policy on the function (`lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` for `cloudfront.amazonaws.com`, scoped by `AWS:SourceArn` of the distribution). For `PUT`/`POST`, "your users must compute the SHA256 of the body and include the payload hash value of the request body in the `x-amz-content-sha256` header when sending the request to CloudFront. Lambda doesn't support unsigned payloads." So a plain HTML `<form method=POST>` will not work through OAC; the page would need JavaScript (fetch with a computed hash). Source: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html . The doc also says the policy must be added with the AWS CLI (console editing unsupported); whether CloudFormation/CDK covers this is not stated in what was read, so **UNVERIFIED** (the CDK docs were not searched for L2 support; ticket for CDK shape can check `aws-cloudfront-origins` `FunctionUrlOrigin.withOriginAccessControl`, UNVERIFIED).
4. **The existing wildcard cert covers `polls.natenite.net`.** CloudFront checks that the SAN has "an exact match for the alternate domain name, or contain a wildcard at the same level". `*.natenite.net` covers `polls.natenite.net` (one level), but not the apex (the repo cert lists apex separately, which is why it works today). Sources: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html and https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html . Viewer certs for CloudFront must be in us-east-1 (same cnames-and-https-requirements page); the repo cert is already there. "Only one certificate can be attached to a CloudFront distribution at a time" (CNAMEs page), which is fine here. Whether the same cert can be attached to several distributions at once is **UNVERIFIED** (not stated in the pages read; commonly done but not confirmed).

## Comparison table

| Dimension | 1. S3+CF + HTTP API + Lambda | 2. S3+CF + Lambda Function URL (OAC) | 3. Single Lambda (HTML+API) | 4. App Runner (container) |
|---|---|---|---|---|
| Availability | GA | GA | GA | **Closed to new customers** (see above) |
| Idle cost | ~$0 (pay per request) | ~$0 | ~$0 | Provisioned memory billed while idle: see cost section, ~$2.6/mo at smallest size |
| Per-request cost | Lambda $0.20/M + $0.0000166667/GB-s (x86) + HTTP API $1.00/M | Lambda only | Lambda only (+ API GW $1/M if API GW fronts it) | vCPU/GB-hour while active |
| Custom domain / TLS | CloudFront alt name, reuse existing us-east-1 wildcard cert. (HTTP API can also have its own regional custom domain, needs regional ACM cert in the API's region.) | CloudFront alt name, reuse cert | Via CloudFront (reuse cert), or API GW regional custom domain; a bare Function URL has no custom-domain feature described in the Lambda docs (UNVERIFIED that none exists) | App Runner issues its own ACM cert via validation CNAMEs; does not use the existing cert (UNVERIFIED whether it can import one) |
| WAF | On CloudFront only (HTTP API cannot take WAF) | On CloudFront (Function URL itself has no WAF association, UNVERIFIED but WAF supported-resource list does not include it) | Only if behind CloudFront (or REST API) | Supported: one web ACL per service via AssociateWebACL |
| Direct-access bypass of CloudFront | Needs secret origin header (CF custom header) or equivalent; API GW execute-api endpoint can be disabled (UNVERIFIED) | OAC + AWS_IAM blocks direct calls | Same as 1 or 2 | n/a (service URL is public) |
| Cold starts | Lambda cold starts (docs: occur in under 1% of invocations, more common in dev/test) | Same | Same, and HTML responses also hit it | Scale-down keeps CPU-throttled instances (no cold start in the Lambda sense) |
| Ops burden | Low | Low (plus POST payload-hash constraint) | Low | Container build/registry/deploys |
| Fit with existing CDK | Add a second behavior or distribution; new Lambda + HTTP API constructs | Same, fewer parts | Fewer parts, HTML mixed with code | New service type, not in the repo's pattern; would need ECR/image pipeline |

## Per-option notes

### 1. S3 + CloudFront + API Gateway HTTP API + Lambda
- HTTP API: $1.00 per million requests, first tier (https://aws.amazon.com/api-gateway/pricing/, HTTP API pricing example; region not named on page, so us-east-1 is **UNVERIFIED**). Free tier is 1M HTTP API calls/month for 12 months after sign-up, new customers only (same page); this account is likely past it.
- No WAF on HTTP API (above). To stay behind the repo's WAF the HTTP API would be an origin of CloudFront. CloudFront-to-origin restriction would rely on an origin custom header (https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/add-origin-custom-headers.html), which is a shared secret rather than IAM.
- Custom domain on the API itself (without CloudFront): a regional custom domain, TLS 1.2 only, requires an ACM cert "from the same region" (https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-custom-domain-names.html, plus search-result summary of the regional custom-domain page). The existing cert is in us-east-1; this works only if the API is also in us-east-1 (it would be).
- API Gateway adds throttling and built-in request queuing ("up to 10,000 requests per second per region by default"), per https://docs.aws.amazon.com/lambda/latest/dg/furls-http-invoke-decision.html .

### 2. S3 + CloudFront + Lambda Function URL via OAC
- Function URL has no endpoint charge: "no additional charges for the URL endpoint itself" (furls-http-invoke-decision page above).
- Function URL scaling is bounded only by the function's concurrency limit, then HTTP 429, with no queueing (same page). A concurrency cap on the function is the lever for abuse (not researched in detail; the Lambda "Throttling function URLs" section exists at https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html but was not read).
- OAC POST constraint as in headline finding 3. Impact: the poll form must submit via JS that sets `x-amz-content-sha256`. A newer "Lambda Web Function" origin type exists with a different OAC configuration (https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda-web.html); its details were not read, so applicability is **UNVERIFIED**.
- Public (AuthType NONE) function URL behind CloudFront is possible but leaves the raw `*.lambda-url.us-east-1.on.aws` URL callable, bypassing WAF. The AWS Config / Security Hub controls referenced (CloudFront.16, `cloudfront-origin-lambda-url-oac-enabled`) encourage OAC (https://docs.aws.amazon.com/securityhub/latest/userguide/cloudfront-controls.html).

### 3. Single Lambda serving HTML and API
- Same plumbing as option 2 or 1, with the HTML rendered by the function instead of S3. The Lambda docs recommend Function URLs "for simple applications or prototyping" and API Gateway "for production applications at scale" or where custom domains/throttling/etc. are needed (furls-http-invoke-decision page). Every page view costs an invocation and passes through WAF/CloudFront with caching off or tuned.
- Cost at this scale is the same order as option 2.

### 4. App Runner
- Status: closed to new customers (above). Existing customers can still create services. Do not plan on it unless the account already uses App Runner.
- WAF: supported. "An App Runner service can be associated with only one web ACL. However, you can associate one web ACL with multiple App Runner services and with multiple AWS resources" (https://docs.aws.amazon.com/apprunner/latest/dg/waf.html). Whether an existing CLOUDFRONT-scope ACL can be reused is **UNVERIFIED** and likely not, since CLOUDFRONT-scope ACLs are for CloudFront (https://docs.aws.amazon.com/waf/latest/APIReference/API_AssociateWebACL.html says CloudFront uses UpdateDistribution); a regional ACL would be a new ACL (new ACL fee).
- Custom domain/certificate: App Runner creates certificate validation CNAME records and DNS target records; for Route 53 the console configures them automatically; ACM is used behind the scenes; auto-renewal needs the validation records left in DNS; CAA must reference `amazon.com`. A wildcard association (`*.example.com`) is possible but a more specific domain overrides it (https://docs.aws.amazon.com/apprunner/latest/dg/manage-custom-domains.html). It does not describe reusing an existing ACM cert, so reuse of the repo's cert is **UNVERIFIED / appears unsupported**.
- Sizes: smallest config is 0.25 vCPU / 0.5 GB (https://docs.aws.amazon.com/apprunner/latest/dg/architecture.html).
- Price (us-east-1, https://aws.amazon.com/apprunner/pricing/): provisioned container instance memory $0.007/GB-hour; active instances $0.064/vCPU-hour + $0.007/GB-hour. Automatic deployments and build fees exist but the amounts were not captured (**UNVERIFIED**). Docs say the service "scales down to CPU-throttled instances when no requests are incoming" (search-result summary of https://docs.aws.amazon.com/apprunner/latest/dg/what-is-apprunner.html); that the minimum provisioned count is 1 was not confirmed (**UNVERIFIED**).
- AWS's replacement, ECS Express Mode, provisions Fargate service + ALB + auto scaling; "no additional charge" for Express Mode, you pay for the resources (apprunner-availability-change page). An ALB is an always-on cost (ALB price not researched, **UNVERIFIED**), so it violates the "avoid new always-on spend" preference in the map.

## Rough monthly cost at about 1,000 responses/month

Assumptions (mine, not from the brief): about 3 requests per response (page load, assets, one POST), so about 3,000 requests/month; each Lambda run 128 MB, about 100 ms; storage cost excluded (ticket 02). All figures are order-of-magnitude.

| Item | Source | Opt 1 | Opt 2/3 | Opt 4 |
|---|---|---|---|---|
| Lambda requests | $0.20/M; 1M/month free (https://aws.amazon.com/lambda/pricing/) | $0 (inside free tier) | $0 | n/a |
| Lambda duration | $0.0000166667/GB-s; 400,000 GB-s free (same page) | $0 | $0 | n/a |
| HTTP API | $1.00/M (API GW pricing page) | ~$0.003 | n/a | n/a |
| WAF per-request | $0.60/M (https://aws.amazon.com/waf/pricing/) | ~$0.002 | ~$0.002 | ~$0.002 |
| WAF ACL if dedicated | $5/ACL/month + $1/rule/month; existing ACL has 2 managed rule groups so +$7/month (same page, from its examples) | $0 if existing ACL reused, else ~$7 | same | ~$7 (new regional ACL) if WAF wanted |
| CloudFront | Pay-as-you-go request/transfer rates not captured (the fetched page only showed flat-rate plans; the Free flat-rate plan is $0, 1M requests, 100 GB, 5 WAF rules). At 3,000 requests the charge is negligible but unverified. | ~$0 (UNVERIFIED) | ~$0 (UNVERIFIED) | n/a |
| App Runner provisioned memory | 0.5 GB x $0.007 x ~730 h | n/a | n/a | ~$2.56 idle |
| App Runner active compute | 0.25 vCPU x $0.064 + 0.5 GB x $0.007 = $0.0195/h while active | n/a | n/a | cents if active only a few hours |
| **Approx total (excl. storage)** | | **< $0.01** (shared ACL), ~$7 (dedicated ACL) | **< $0.01** (shared ACL), ~$7 (dedicated) | **~$2.6 to $3**, ~$10 with a dedicated ACL |

Note: App Runner total also depends on whether the account is eligible at all.

## Reuse of cert, zone and WAF (what is and is not established)

- Cert: `*.natenite.net` SAN already covers `polls.natenite.net` (verified, CloudFront CNAMEs page). For CloudFront, nothing new to issue. For API Gateway regional domain: cert in the same region (us-east-1) works. For App Runner: separate cert/validation (appears so).
- Hosted zone: Route 53 alias records to a CloudFront distribution are what `SiteStack` already uses for apex and www; the same pattern would add a `polls` record. An alias record is also what App Runner recommends for root domains and works for subdomains (manage-custom-domains page). Route 53 does not charge for alias queries (same page).
- Same distribution vs new distribution: adding `polls.natenite.net` as a third alternate domain name on the existing distribution is permitted by the cert check, but the existing behavior is S3 + URL rewrite for the static site, so host-based routing would be needed. This trade-off, and whether the existing web ACL can be shared by a second distribution, is **UNVERIFIED** (not researched).
- WAF: the repo's ACL is CLOUDFRONT scope with two AWS managed rule groups. It protects only CloudFront-fronted designs (options 1 to 3 behind CloudFront). Rate-based rules exist for per-IP limiting (https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-wafv2-webacl-ratebasedstatement.html); each added rule costs about $1/month by the pricing page above.

## What this leaves undecided

- Whether this AWS account is an "existing" App Runner customer (only matters if option 4 is still wanted).
- Same CloudFront distribution as the main site (host-based routing) vs a second distribution for `polls.natenite.net`, and whether one web ACL and one cert can be shared across both (UNVERIFIED).
- Option 1 vs 2 vs 3 itself. Key trade-off: HTTP API adds a $1/M hop, a shared-secret origin header and queueing/throttling but cannot take WAF; Function URL + OAC is cheaper and IAM-locked but forces JS-signed POST bodies (`x-amz-content-sha256`).
- Whether the form must work without JavaScript (affects OAC feasibility).
- Whether CDK supports OAC for Lambda function URLs and the Lambda permission natively (not checked).
- Exact CloudFront pay-as-you-go pricing and whether the account is on a flat-rate plan (pricing MCP unavailable; the page only showed flat-rate plans).
- Abuse controls: per-IP rate rule cost vs Lambda reserved concurrency as a cost cap.
- Cold-start tolerance for a form submit (docs say under 1% of invocations, https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html; actual Python/Node runtime latency not measured).
- Storage choice and the email field's handling (tickets 02 and 03).

## Sources index

- https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html
- https://docs.aws.amazon.com/apprunner/latest/dg/manage-custom-domains.html
- https://docs.aws.amazon.com/apprunner/latest/dg/waf.html
- https://docs.aws.amazon.com/apprunner/latest/dg/architecture.html
- https://docs.aws.amazon.com/apprunner/latest/dg/what-is-apprunner.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/add-origin-custom-headers.html
- https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-custom-domain-names.html
- https://docs.aws.amazon.com/lambda/latest/dg/furls-http-invoke-decision.html
- https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html
- https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html
- https://aws.amazon.com/lambda/pricing/ , https://aws.amazon.com/api-gateway/pricing/ , https://aws.amazon.com/apprunner/pricing/ , https://aws.amazon.com/waf/pricing/ , https://aws.amazon.com/cloudfront/pricing/ (page fetches; Price List API unavailable due to expired SSO)
