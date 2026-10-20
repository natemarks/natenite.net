# R07: Documentation verification of UNVERIFIED items

Scope: close UNVERIFIED claims from R01, R02, R05 and the map using the aws-docs and aws-iac MCP servers. Pages were read (not only snippets). Prices are out of scope. No decision is recommended here. Date of reading: 2026-10-15; CDK docs read were aws-cdk-lib 2.273.0 (the version the earlier tickets cite).

Status key: VERIFIED / PARTIAL / STILL UNVERIFIED / CONTRADICTS EARLIER FINDING.

## Summary table

| # | Item | Status |
|---|------|--------|
| 1a | CDK/CFN can configure OAC for a Lambda Function URL origin, plus both Lambda permissions | VERIFIED (and R01's "CLI only" worry is moot for CDK) |
| 1b | Lambda Web Function OAC removes the `x-amz-content-sha256` POST requirement | VERIFIED, but Web Functions are Node.js only today (new constraint) |
| 2a | One ACM cert on several CloudFront distributions | VERIFIED |
| 2b | One WAF web ACL on several CloudFront distributions | VERIFIED |
| 2c | polls.natenite.net as a 3rd alternate name on the existing distribution | VERIFIED as allowed; host routing needs a CloudFront Function (behaviors are path-only) |
| 3a | S3 `If-None-Match` failure code | VERIFIED: 412, with a 409 edge case |
| 3b | S3 default SSE-S3 since Jan 2023 | VERIFIED |
| 4 | DynamoDB PITR window | VERIFIED (35 days max and default, but PITR is OFF by default); deleted-item persistence PARTIAL |
| 5a | ECS Express `MinTaskCount` accepts 0 | STILL UNVERIFIED |
| 5b | Internal Express ALB usable as CloudFront VPC origin | PARTIAL |
| 5c | L2 CDK construct for Express | VERIFIED absent in aws-cdk-lib 2.273.0 (L1 only) |
| 6 | Lightsail containers: existing ACM cert, WAF, CloudFront | Cert: PARTIAL (docs only describe Lightsail-created certs); WAF: STILL UNVERIFIED; CloudFront: PARTIAL |
| 7a | Lambda reserved concurrency as a cap | VERIFIED, with a function-URL RPS formula |
| 7b | WAF rate-based rule semantics | VERIFIED |
| 8 | App Runner "existing customer" definition | STILL UNVERIFIED (docs give no definition) |

## Earlier claims that are wrong, outdated or need a caveat

1. R01 headline 3 / R05 comparison row ("a plain HTML form POST will not work through OAC; the page needs JS to set `x-amz-content-sha256`"): CORRECT for Lambda **function URL** OACs (still says "Lambda doesn't support unsigned payloads"), but **no longer the whole story**. The newer Lambda **Web Function** origin type signs POST/PUT/PATCH with `UNSIGNED-PAYLOAD` and says "You do not need to include an `x-amz-content-sha256` header in requests to CloudFront". So a plain form POST works there. Catch not in R01: "AWS Lambda Web Functions currently support Node.js runtimes only."
2. R01 headline 3 ("whether CloudFormation/CDK covers this is not stated, UNVERIFIED"): resolved, CDK has an L2 that adds the permissions (item 1a).
3. R05 ("Express creates no WAF resource. Whether Express tolerates an external WAF association: UNVERIFIED"): the Express best-practices page documents associating a web ACL with the Express ALB (item 5d). One constraint R05 did not have: a web ACL associated with a CloudFront distribution cannot be associated with any other resource type (an ALB), so CloudFront and ALB cannot share one ACL.
4. R01 "Lambda reserved concurrency" was not stated, but note terminology drift: the current Lambda docs call classic functions "Event Functions". Any ticket text that says "Lambda function" and links the older docs may be reading the Event Function pages.
5. R02 line 61 ("S3 default encryption not read, UNVERIFIED") and line 64 ("PITR window length not read") are now closed (items 3b and 4).
6. Nothing else earlier was contradicted.

## 1. CloudFront OAC for Lambda

### 1a. Function URL origin with OAC: CDK, CloudFormation, permissions. VERIFIED

- CloudFormation: `AWS::CloudFront::OriginAccessControl` with `OriginAccessControlOriginType: lambda`, `SigningBehavior: always`, `SigningProtocol: sigv4`. Page: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html (CloudFormation tab). Quote: "Type: AWS::CloudFront::OriginAccessControl ... OriginAccessControlOriginType: lambda  SigningBehavior: always  SigningProtocol: sigv4".
- The function URL must be IAM-auth: "To use OAC, you must specify `AWS_IAM` as the value for the `AuthType` parameter." (same page, Prerequisites).
- Required permissions, same page: two `aws lambda add-permission` calls for principal `cloudfront.amazonaws.com`, one with action `lambda:InvokeFunctionUrl`, one with `lambda:InvokeFunction`, each with `--source-arn arn:aws:cloudfront::<acct>:distribution/<id>`. The page says the Lambda console cannot edit this policy ("you must use the AWS CLI"), which is the origin of R01's worry, but that restriction is about hand-editing, not about IaC.
- CDK L2: `FunctionUrlOrigin.withOriginAccessControl(fnUrl, {originAccessControl: oac})` exists, with `FunctionUrlOriginAccessControl` (L2 OAC, `signing: Signing.SIGV4_ALWAYS`) in `aws_cloudfront`. Python form: `origins.FunctionUrlOrigin.with_origin_access_control(fn_url, origin_access_control=oac)`. If you omit `origin_access_control`, the docs say "an Origin Access Control will be created." Sources: https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/FunctionUrlOrigin?lang=python&submodule=aws_cloudfront_origins and the README at https://constructs.dev/packages/aws-cdk-lib/v/2.273.0?submodule=aws_cloudfront_origins&lang=python .
- Permissions are added by the L2. Quote (aws_cloudfront_origins README, "Function URL permissions"): "Lambda requires both `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` for CloudFront to call a newly created function URL through OAC. `FunctionUrlOrigin.withOriginAccessControl` adds both permissions." The `bind()` method takes `distributionId` for this ("used to grant origin access permissions to the distribution").
- Still holds for function URLs (R01): POST needs a client-computed body hash. Quote: "If you use `PUT` or `POST` methods with your Lambda function URL, your users must compute the SHA256 of the body and include the payload hash value of the request body in the `x-amz-content-sha256` header when sending the request to CloudFront. Lambda doesn't support unsigned payloads."

### 1b. Lambda Web Function OAC page. VERIFIED (answers the POST question), with a runtime constraint

Page: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda-web.html

- POST: "For `PUT`, `POST`, and `PATCH` requests, CloudFront signs the origin request with an unsigned payload (`UNSIGNED-PAYLOAD`). The request body is not covered by the CloudFront signature... You do not need to include an `x-amz-content-sha256` header in requests to CloudFront. If a viewer sends one, CloudFront does not use it when signing the origin request." So a plain HTML form POST is fine on this origin type.
- Different OAC config from function URLs: `OriginAccessControlOriginType: lambda`, `SigningBehavior: always-amz-auth` (only this one is supported; "`always`, `never`, and `no-override` are not supported"; "`always-amz-auth` is not supported for any other origin type, including Lambda function URL origins"), `SigningProtocol: sigv4` (regional) or `sigv4a` (global endpoint). CloudFormation example is on the page. Whether the CDK L2 (`FunctionUrlOriginAccessControl`/`Signing`) exposes `always-amz-auth` for Web Functions was **not found** in the docs read; the L1 `CfnOriginAccessControl` takes free-form strings, so it would work at L1 (inference, not stated in a doc).
- Permission: different from function URLs. Action is `lambda:InvokeWebFunctionEndpoint`, principal `cloudfront.amazonaws.com`, `aws:SourceArn` = distribution ARN, attached "with the **put-resource-policy** command with the *function* ARN" using `aws lambda-web put-resource-policy`. No CDK/CFN resource for this policy was found in the docs read (STILL UNVERIFIED for IaC; also no L2 for Web Functions found).
- Origin request policy must exclude the viewer Host header ("use `AllViewerExceptHostHeader`, not `AllViewer`"); Lambda@Edge origin-request/response triggers are not supported on these behaviors.
- Runtime limit (new, not in R01): https://docs.aws.amazon.com/lambda/latest/dg/web-functions.html : "AWS Lambda Web Functions currently support Node.js runtimes only. If you use Java, Python, .NET, or another language, see ... Lambda Event Functions ... or AWS Lambda MicroVMs". Zip deploy only. Python function-URL (Event Function) apps do not get the no-hash POST behavior.
- Web Function throttling controls (useful for abuse cap, item 7): endpoint `rateLimit` (0 to 10,000 RPS, multiples of 100 up to 1,000; 429 above it) and `maxEnvironments` (2 to 10,000); "There is no minimum or reserved-environment setting... scales to zero". Source: https://docs.aws.amazon.com/lambda/latest/dg/web-functions-scaling.html . These are set via `aws lambda-web update-web-function-endpoint`; IaC coverage not checked.
- WAF and custom domains for Web Functions: "To use a custom domain or AWS WAF protection, put an Amazon CloudFront distribution in front of the endpoint." (web-functions.html).
- Not verified: whether Web Functions are GA vs preview (the pages show no preview banner in the text read).

## 2. One cert and one WAF ACL on multiple distributions; third alternate name; host routing

### 2a. Same ACM cert on multiple distributions. VERIFIED
https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-limits.html : "**Use the same certificate for multiple CloudFront distributions**: You can use the same certificate for any or all of the CloudFront distributions that you're using to serve HTTPS requests... You can associate only one certificate with each distribution. Each distribution must include one or more alternate domain names that also appear in the Common Name field or the Subject Alternative Names field in the certificate." Same account only for ACM certs ("If you're using certificates provided by ACM, you can't configure CloudFront to use certificates that were created by a different AWS account").

### 2b. Same WAF ACL on multiple distributions. VERIFIED
https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-associating-aws-resource.html : "You can associate a protection pack (web ACL) with one or more CloudFront distributions. You cannot associate a protection pack (web ACL) that you have associated with a CloudFront distribution with any other AWS resource type." Also: each resource can have only one ACL.
Rate-based rules are tracked per rule instance ("AWS WAF tracks and manages web requests separately for each instance of a rate-based rule... if you provide the same rate-based rule settings in two web ACLs, each... gets its own tracking"). Inference (not stated): in one shared ACL a rate rule counts across both hosts unless a scope-down statement matches on Host.

### 2c. polls.natenite.net as a third alternate name on the existing distribution. VERIFIED as allowed; routing is the real cost
- Cert coverage (confirms R01 headline 4): https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html : with `*.example.com` on the cert, "you can add any alternate domain name... that replaces the wildcard at that level, including marketing.example.com... However, you can't add... example.com or marketing.product.example.com." One cert per distribution ("Only one certificate can be attached to a CloudFront distribution at a time").
- Duplicate names: "You cannot add an alternate domain name to a CloudFront distribution if the same alternate domain name already exists in another CloudFront distribution". Wildcard overlap across distributions is allowed and the more specific name wins.
- How CloudFront picks a distribution: by `Host` header (CNAMEs page, "How CloudFront identifies the distribution for a request").
- Cache behaviors are **path-pattern only**. https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesCacheBehavior.html : "A path pattern ... specifies to which requests you want this cache behavior to apply... The first match determines which cache behavior is applied... the default cache behavior is always the last to be processed." There is no host dimension, so one distribution serving two hostnames from different origins at the same paths cannot split on host with behaviors alone.
- Host-based routing option: a viewer-request CloudFront Function can read the Host header and call `cf.selectRequestOriginById("<origin id>")` or `updateRequestOrigin()`. https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/helper-functions-origin-modification.html : "`selectRequestOriginById()` ... selecting a different origin that's already configured in your distribution." Limits: viewer-request only, requires JavaScript runtime 2.0 (`import cf from 'cloudfront'`), "This method only accepts origins that are already defined in the same distribution", and runs on every request. Note the existing repo function (`stack/site.py`) is a runtime-1-style viewer-request rewrite attached to the default behavior; it would have to be extended or replaced (it would otherwise append `index.html` to poll paths). Also `updateRequestOrigin()` cannot be used on VPC origins ("The request will fail").
- Path-based alternative (no function): put poll traffic under a path prefix on the existing host (a behavior such as `/polls/*`); this changes the URL shape from `polls.natenite.net/<id>`. Mentioned only because it is the documented native mechanism.
- Per-origin OAC: OAC is set per origin (`OriginAccessControlId` inside an origin, per the Lambda OAC page's API section), so an S3 OAC origin and a Lambda OAC origin can coexist in one distribution. The existing stack uses `add_property_override` on `Origins.0` for the S3 OAC, which would need care when a second origin is added (index-based override; code observation, not a doc claim).
- Not found: a documented quota for number of alternate names or behaviors in the pages read (they link to https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html, not read).

## 3. S3 conditional writes and default encryption

### 3a. `If-None-Match` failure semantics. VERIFIED
https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html
- "If there's an existing object, the write operation fails, resulting in a `412 Precondition Failed` response." Versioned buckets: same, unless the current version is a delete marker (then it succeeds).
- Concurrent writers: "the first write operation to finish succeeds. Amazon S3 then fails subsequent writes with a `412 Precondition Failed`."
- 409 case: "You can also receive a `409 Conflict` response in the case of concurrent requests if a delete request to an object succeeds before a conditional write operation on that object completes. When using conditional writes with `PutObject`, uploads may be retried after receiving a `409 Conflict` error."
- Value must be `*`: "The `If-None-Match` header expects the * (asterisk) value." Requires SigV4 and `s3:PutObject` only. Works for `PutObject`, `CompleteMultipartUpload`, `CopyObject`. "The HTTP `If-None-Match` header only applies to the current version of an object in a version bucket."
- A bucket policy can require the header: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html (`s3:if-none-match` condition key; not fully read beyond the search summary).
- Related, for the CloudFront angle: the CloudFront page https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/http-412-precondition-failed.html exists for CloudFront-originated 412s (not read in detail).

### 3b. S3 default encryption. VERIFIED
https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-encryption.html : "Amazon S3 now applies server-side encryption with Amazon S3 managed keys (SSE-S3) as the base level of encryption for every bucket in Amazon S3. Starting January 5, 2023, all new object uploads to Amazon S3 are automatically encrypted at no additional cost and with no impact on performance." (The repo's `SiteStack` also sets `S3_MANAGED` explicitly.)

## 4. DynamoDB PITR

- Window: VERIFIED. https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html : "provide up to 35 days of recovery points at a per second granularity... By default, your `RecoveryPeriodinDays` is 35. However, you can set it to be any value between 1 and 35." Changing the period does not change price (same page and https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html).
- PITR is not on by default. Howitworks page: "`PointInTimeRecoveryStatus`, which is `DISABLED` by default until you enable PITR. A newly created table therefore reports `ContinuousBackupsStatus` as `ENABLED` together with `PointInTimeRecoveryStatus` as `DISABLED`." CloudFormation property: `PointInTimeRecoverySpecification: {PointInTimeRecoveryEnabled: true, RecoveryPeriodInDays: 35}` (same page). Retention is a rolling window: lowering the period immediately makes older backups unrecoverable.
- Deleted items persist in PITR backups: PARTIAL. No page read has a sentence saying "deleted items remain in backups". The behavior is implied: you can restore to any second in the window ("restore to any point in time within `EarliestRestorableDateTime` and `LatestRestorableDateTime`"), so an item deleted at time T exists in restore points before T until those age out. This supports R02's privacy caveat that deleted personal data (emails) lives in PITR for up to the retention window. Restores always create a new table (Howitworks and https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.Tutorial.html), so there is no in-place "purge a deleted item from backups"; shortening `RecoveryPeriodInDays` (1 to 35) is the documented lever on how long that data persists. Deleting a PITR-enabled table also creates a system backup retained 35 days (Howitworks, "Delete a table with PITR enabled").

## 5. ECS Express Mode

### 5a. `MinTaskCount` accepts 0. STILL UNVERIFIED
- `ExpressGatewayScalingTarget.MinTaskCount`: "The minimum number of tasks to run in the Express service." Type Integer, not required, no range or minimum stated. https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-expressgatewayservice-expressgatewayscalingtarget.html and https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ExpressGatewayScalingTarget.html .
- Defaults page: "desiredMinTaskCount: 1 - Minimum number of tasks to maintain"; "desiredCount: Express Mode service -> MinTasks (default is 1)"; max default 20. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html . Best-practices page only talks about raising the minimum to 3 for production. No doc says 0 is allowed or rejected. Nothing in the docs describes request-driven wake-from-zero for Express either; its default metric is CPU (target 60) and the other options are memory and `REQUEST_COUNT_PER_TARGET`, all of which need a running task to emit a metric.
- Express also creates an ALB, which is not removable (listed in the resource list; the ALB is shared by up to 25 Express services in a VPC and de-provisioned when no Express services remain: "Up to 25 Express Mode services in the same VPC can share an Application Load Balancer... Express Mode will also deprovision unused Application Load Balancers").

### 5b. Internal ALB as a CloudFront VPC origin. PARTIAL
- Express makes an internal ALB from private subnets: express-service-work page, "Network configuration defaults": "If you provide private subnets (subnets without an internet gateway in their route table), Express Mode will provision an internal ALB." Also "assignPublicIp ... is disabled if you provide a private subnet, and you are then responsible for configuring a NAT gateway if your tasks need internet access." The first Express service in a VPC fixes whether the shared ALB is internal or internet-facing ("the first Express Mode service for a VPC defines the subnets associated with either the internet-facing or internal load balancer for that VPC").
- CloudFront can use an internal ALB as a VPC origin: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html : "You can use Application Load Balancers (ALBs), Network Load Balancers (NLBs), and EC2 instances in private subnets as VPC origins." Requirements: VPC with an internet gateway; private subnet with a free IPv4 for a service-managed ENI ("no additional cost for them"); resource must be Active; security group on the ALB must allow the `com.amazonaws.global.cloudfront.origin-facing` prefix list or the service-managed `CloudFront-VPCOrigins-Service-SG`; VPC origin creation can take up to 15 minutes. Not supported: gRPC, Lambda@Edge origin triggers, NACL inbound evaluation.
- Not found in any page: an explicit statement that an Express-managed ALB can be referenced by a CloudFront VPC origin (or that Express will not fight edits to the ALB security group). The ALB's listener is HTTPS 443 with an Express-issued ACM cert for the `*.ecs.<region>.on.aws` name; CloudFront-to-origin TLS name matching was not resolved (the origin-side cert issue in R05 remains open).

### 5c. L2 CDK construct for Express. VERIFIED absent (as of aws-cdk-lib 2.273.0 docs)
Searches of the CDK docs and samples (aws-iac MCP) returned only the L1 `aws_ecs.CfnExpressGatewayService` (props `infrastructure_role_arn`, `cluster`, `cpu`, `execution_role_arn`, `health_check_path`, `network_configuration`, `primary_container`, scaling target, `task_role_arn`, ...). https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/CfnExpressGatewayService?lang=python&submodule=aws_ecs . No `ExpressGatewayService` L2 or ecs-patterns Express construct appeared. This is an absence-of-result finding, not a doc statement that none exists.

### 5d. WAF on Express (resolves an R05 UNVERIFIED)
https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-best-practices.html : "**Use AWS WAF for web applications**... You can enable this by creating a Web ACL and then associating it to the Application Load Balancer used by your Express Mode service." (`aws wafv2 associate-web-acl --resource-arn <alb>`). Caveat from item 2b: the ALB would need its own regional ACL, separate from the CloudFront ACL. Whether CDK/CFN-managed association interferes with Express's own management of the ALB is not stated.

## 6. Lightsail containers

- Existing ACM certificate: PARTIAL, leaning no. https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-tls-ssl-certificates-in-lightsail-https.html : the certificates are "created in Lightsail"; they "are issued by the AWS Certificate Manager (ACM) service" but the process is: "Create a certificate for your domain using Lightsail. Validate the certificate by adding a canonical name (CNAME) record... Attach the validated certificate". https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-enabling-container-services-custom-domains.html : "choose the Lightsail SSL/TLS certificate that you created for the domains"; "up to 4 custom domains with each of your Lightsail container services, and you cannot use the same domains on more than one service." No page read describes importing or referencing an account ACM certificate. (R05 said the same; this stays "not documented".)
- WAF: STILL UNVERIFIED. Searched; no page associates WAF with Lightsail container services, and the WAF "supported resources" list read (https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-associating-aws-resource.html) does not include Lightsail (API Gateway REST, ALB, AppSync, Cognito user pool, App Runner, AgentCore Gateway, Verified Access, Amplify, plus CloudFront). Absence from that list is evidence, not a statement of non-support for Lightsail.
- CloudFront in front: PARTIAL. Documented path is Lightsail's own CDN distribution (CloudFront-based but a Lightsail resource): https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-containers.html : "You can use Lightsail container services as the origin for Lightsail CDN distributions." Docs for a general account CloudFront distribution with a Lightsail container origin were not found; the default `https://<service>.<guid>.<region>.cs.amazonlightsail.com` endpoint is a public HTTPS endpoint (container-services page), so it is technically a custom-origin candidate (inference only). Domain caveat from the custom-domains page: when the origin is a Lightsail distribution, Lightsail "automatically adds the default domain name of your distribution as a custom domain on your container service" (the 4-domain budget counts it).
- Other documented facts: Lightsail container pricing is fixed per node whether "enabled or disabled, and whether it has a deployment or not"; no private-registry pulls ("only public container registries are supported") and no alerting on metrics. (Quotes: container-services page and FAQ.) CDK is L1 `CfnContainer` only per R05 (not re-verified).

## 7. Abuse and cost caps

### 7a. Lambda reserved concurrency. VERIFIED (with a formula)
- https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html : "Reserved concurrency acts as both a lower and upper bound - it reserves the specified capacity exclusively for your function while also preventing it from scaling beyond that limit. Configuring reserved concurrency for a function incurs no additional charges." Also "To intentionally throttle an Event Function, set its reserved concurrency to 0." You can reserve at most unreserved account concurrency minus 100.
- Function URL specifics: https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html : "Your function's maximum request rate per second (RPS) is equivalent to 10 times the configured reserved concurrency. For example, if you configure your function with a reserved concurrency of 100, then the maximum RPS is 1,000. Whenever your function concurrency exceeds the reserved concurrency, your function URL returns an HTTP `429`."
- Caveats: this caps spend only indirectly (bounded concurrency and RPS, not a dollar budget; 429s still count as CloudFront requests and WAF requests). Applies to Event Functions; Web Functions use `maxEnvironments` and `rateLimit` instead (item 1b).

### 7b. WAF rate-based rule semantics. VERIFIED
https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-high-level-settings.html :
- Evaluation window: "Valid settings are 60 (1 minute), 120 (2 minutes), 300 (5 minutes), and 600 (10 minutes), and 300 (5 minutes) is the default." Window is a look-back, not how often WAF checks.
- Minimum limit: "The lowest limit setting allowed is 10." (requests per window, per aggregation instance).
- Aggregation: per aggregation key; IP, forwarded IP header, custom keys, or "Count all"; scope-down statement required with Count all. Action: "any rule action except Allow".
- Cost of rule: "WCUs - 2, as a base cost. For each custom aggregation key that you specify, add 30 WCUs" (https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html).
- Accuracy: https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html : "not intended for precise request-rate limiting"; "it's possible for requests to be coming in at too high a rate for up to several minutes before AWS WAF detects and rate limits them... Usually, this delay is below 30 seconds."; changing settings resets counts.
- Implication for the repo: the existing `SiteStack` ACL has only two managed rule groups (Common, KnownBadInputs) and no rate-based rule (code observation). Per-IP rate limiting on CloudFront is therefore an addition to the ACL, which is shared if the same ACL is attached to a second distribution.

## 8. App Runner "existing customers". STILL UNVERIFIED
https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html : "AWS App Runner is no longer open to new customers. Existing customers can continue to use the service as normal, including creating new resources and services... If you're not an existing customer, AWS recommends Amazon ECS Express Mode." The page defines neither "existing customer" nor any cut-off criterion (account, organization, prior service usage). R01's snippet-based date (April 30, 2026) was not re-checked against the release notes; this page has no date. Only the account owner (console or support) can answer whether this account qualifies.

## Impact on the Lambda-vs-container picture (facts only)

- The R01/R05 argument that a Lambda form POST through OAC needs JavaScript is now conditional on origin type: function URL (any runtime, hash required) vs Web Function (no hash needed, Node.js only).
- The CDK path for function URL + OAC is fully L2 and adds the permissions; the Web Function path has no L2 and its resource policy has no IaC resource found (CLI `aws lambda-web put-resource-policy`).
- Sharing the existing cert and ACL across a second distribution is documented as allowed; so is adding polls.natenite.net to the existing distribution, but only with a Host-based CloudFront Function (or a path-prefix design) for routing.
- Express Mode scale-to-zero remains undocumented; with an always-on ALB the cost-floor argument in R05 is unchanged. Express has no L2; WAF can attach to its ALB but not with the CloudFront ACL.
- Lightsail: no documented WAF, no documented existing-ACM-cert reuse.
- App Runner eligibility cannot be resolved from docs.

## Pages read (primary)

- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda-web.html
- https://docs.aws.amazon.com/lambda/latest/dg/web-functions.html and web-functions-scaling.html
- https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/FunctionUrlOrigin?lang=python&submodule=aws_cloudfront_origins (+ aws_cloudfront_origins README via aws-iac search)
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html , cnames-and-https-limits.html , DownloadDistValuesCacheBehavior.html , helper-functions-origin-modification.html , private-content-vpc-origins.html
- https://docs.aws.amazon.com/waf/latest/developerguide/web-acl-associating-aws-resource.html , waf-rule-statement-type-rate-based.html , ...-high-level-settings.html , ...-caveats.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html , bucket-encryption.html
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html , PointInTimeRecovery_Howitworks.html , PointInTimeRecovery.Tutorial.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html , express-service-best-practices.html ; CloudFormation and API ExpressGatewayScalingTarget pages
- https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-container-services.html , amazon-lightsail-faq-containers.html , amazon-lightsail-enabling-container-services-custom-domains.html , understanding-tls-ssl-certificates-in-lightsail-https.html
- https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html , urls-configuration.html
- https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html
