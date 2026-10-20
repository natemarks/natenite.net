---
status: accepted
---

# Serve poll submissions from a Lambda Function URL behind CloudFront OAC

Poll responses are written by a Python Lambda exposed as a Function URL with `AuthType: AWS_IAM`, reached only through a dedicated CloudFront distribution using Origin Access Control. Poll pages are static files in S3 on the same distribution. We chose this over an HTTP API and a Lambda Web Function because it is the cheapest option, is locked to CloudFront by IAM rather than a shared secret, and is fully expressible in CDK so the golden tests cover every resource.

## Considered options

- **HTTP API + Lambda behind CloudFront.** Works with a plain form POST, but adds $1 per million requests and can only be locked to CloudFront by a shared-secret origin header. HTTP APIs cannot attach WAF, so WAF would sit on CloudFront anyway. ([AWS: HTTP API vs REST API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html))
- **Lambda Web Function + OAC.** POST works without a body hash, but it supports Node.js only ([AWS: Web Functions](https://docs.aws.amazon.com/lambda/latest/dg/web-functions.html)), and its resource policy is attached with `aws lambda-web put-resource-policy`, for which no CDK or CloudFormation resource was found. That would put a step outside the template.
- **Containers (ECS Express Mode, ECS on Fargate, Lightsail).** An always-on ALB or fixed node puts the floor at roughly $7 to $36 a month against a few cents for Lambda. App Runner is closed to new customers ([AWS: App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)). See `.scratch/wayfinder/poll-app/research/05-container-platforms.md` and `06-verified-pricing.md`.

## Consequences

- Function URLs behind OAC require the client to send the SHA-256 of a POST body in `x-amz-content-sha256`, because "Lambda doesn't support unsigned payloads." The submit page must therefore use JavaScript (`fetch` with `crypto.subtle`); a plain HTML form POST will not work. ([AWS: restricting access to a Lambda function URL origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html))
- CDK's `FunctionUrlOrigin.with_origin_access_control` adds both required Lambda permissions (`lambda:InvokeFunctionUrl` and `lambda:InvokeFunction`). ([aws-cdk-lib `FunctionUrlOrigin`](https://constructs.dev/packages/aws-cdk-lib/v/2.273.0/api/FunctionUrlOrigin?lang=python&submodule=aws_cloudfront_origins))
- The raw `*.lambda-url` endpoint cannot be called directly, so WAF on the distribution cannot be bypassed.
- Abuse is capped by a per-IP WAF rate rule plus Lambda reserved concurrency; a function URL returns 429 above 10 times the reserved concurrency in requests per second. ([AWS: function URL configuration](https://docs.aws.amazon.com/lambda/latest/dg/urls-configuration.html))
- If a plain-form, no-JavaScript submit is ever required, revisit this decision: HTTP API behind CloudFront is the fallback that keeps any runtime.
