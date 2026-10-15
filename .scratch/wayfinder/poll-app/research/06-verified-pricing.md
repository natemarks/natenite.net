# 06 - Verified pricing (AWS Price List API, us-east-1)

Source: aws-pricing MCP (`get_pricing`, `get_pricing_attribute_values`), queried 2026-10-15. All prices are USD, OnDemand term, list price (no free tiers, no savings plans, no EDP). Price List publication dates are 2026-09-11 to 2026-10-14 (per-row `publicationDate`). Where a figure is not in the Price List API it is marked NOT IN API.

Citation format: service code | filters | region | SKU | description string returned.

## 1. Verified unit prices

| Item | Price | Citation |
|---|---|---|
| Lambda requests (x86 and ARM) | $0.20 per 1M ($0.0000002 each) | AWSLambda \| group=AWS-Lambda-Requests / AWS-Lambda-Requests-ARM \| us-east-1 \| SKU GU2ZS9HVP6QTQ7KE / K7BX6567RJ67A2KE \| "AWS Lambda - Total Requests - US East (Northern Virginia)" |
| Lambda GB-s x86 | Tier 1 (0 to 6B GB-s) $0.0000166667; Tier 2 (6B to 15B) $0.0000150000; Tier 3 (>15B) $0.0000133334 | AWSLambda \| group=AWS-Lambda-Duration \| us-east-1 \| SKU TG3M4CAGBA3NYQBH \| "AWS Lambda - Total Compute - US East (Northern Virginia)-Tier-1" |
| Lambda GB-s ARM | Tier 1 (0 to 7.5B) $0.0000133334; Tier 2 (7.5B to 18.75B) $0.0000120001; Tier 3 $0.0000106667 | AWSLambda \| group=AWS-Lambda-Duration-ARM \| us-east-1 \| SKU 72SBSFWPMDTH8S3J \| "AWS Lambda - Total Compute for ARM - US East (Northern Virginia)-Tier-1" |
| Lambda free tier | NOT IN API (no $0 tier row returned for any Lambda SKU). Free-tier claims in 01 stay public-page-only. | AWSLambda, same queries |
| API Gateway HTTP API requests | $1.00 per 1M (first 300M); $0.90 per 1M beyond | AmazonApiGateway \| usagetype=USE1-ApiGatewayHttpRequest \| us-east-1 \| SKU FC2TWT2UEPTBKVBX \| "$1/million requests - API Gateway HTTP API (first 300 million)" |
| API Gateway free tier | NOT IN API | same |
| DynamoDB on-demand write | $0.625 per 1M WRU | AmazonDynamoDB \| usagetype=WriteRequestUnits \| us-east-1 \| SKU FGXVD96DKJMUASY3 \| "$0.625 per million write request units (N. Virginia)" |
| DynamoDB on-demand read | $0.125 per 1M RRU | AmazonDynamoDB \| usagetype=ReadRequestUnits \| us-east-1 \| SKU 4W4ZMC46EHE8XTTZ \| "$0.125 per million read request units (N. Virginia)" |
| DynamoDB storage (Standard) | first 25 GB-Mo $0.00; beyond $0.25/GB-Mo | AmazonDynamoDB \| usagetype=TimedStorage-ByteHrs \| us-east-1 \| SKU F3E2EDSYC6ZNW7XP \| "$0.00 per GB-Month of storage for first 25 free GB-Months" / "$0.25 per GB-Month ... beyond" |
| DynamoDB PITR | $0.20 per GB-Mo | AmazonDynamoDB \| usagetype=USE1-TimedPITRStorage-ByteHrs \| us-east-1 \| SKU TFXQN9PEG62G7A67 \| "$0.20 per GB-Month of storage used for DynamoDB PITR backup" |
| DynamoDB export to S3 | $0.10 per GB exported | AmazonDynamoDB \| usagetype=USE1-ExportDataSize-Bytes \| us-east-1 \| SKU 3ADXMU9RYGKRUA9W \| "$0.10000 per GB of data exported in US East (N. Virginia)" |
| S3 PUT/COPY/POST/LIST | $0.005 per 1,000 | AmazonS3 \| usagetype=Requests-Tier1 \| us-east-1 \| SKU E9YHNFENF4XQBZR6 \| "$0.005 per 1,000 PUT, COPY, POST, or LIST requests" |
| S3 GET and other | $0.0004 per 1,000 ($0.004 per 10,000) | AmazonS3 \| usagetype=Requests-Tier2 \| us-east-1 \| SKU ZWQ6Q48CRJXX4FXE \| "$0.004 per 10,000 GET and all other requests" |
| S3 Standard storage, first tier | $0.023/GB-Mo (first 50 TB); $0.022 next 450 TB | AmazonS3 \| usagetype=TimedStorage-ByteHrs, storageClass=General Purpose \| us-east-1 \| SKU WP9ANXZGBYYSGJEA \| "$0.023 per GB - first 50 TB / month of storage used" |
| Athena | $5.00 per TB scanned, 10 MB minimum per successful/cancelled query | AmazonAthena \| usagetype=USE1-DataScannedInTB \| us-east-1 \| SKU B6WHE3FUNCDQVVX4 \| "5.00 USD per Terabytes for DataScannedInTB in US East (N. Virginia)"; product description "minimum 10MB for each successful or cancelled queries" |
| Firehose ingest (service code AmazonKinesisFirehose) | Tier 1 $0.029/GB (0 to 500 TB), $0.025, $0.020. A second SKU, "DirectPUT-no-rounding", is $0.08/GB "ingested or delivered" | AmazonKinesisFirehose \| usagetype=USE1-BilledBytes, operation=PutRecord \| us-east-1 \| SKU 2ZXSJSRZJDEZG2UP \| "Tier 1 $0.029 per GB of data ingested"; and usagetype=USE1-DirectPUT-no-rounding-BilledBytes \| SKU 9QWTRBSJY5J6A9MX \| "Per GB of data ingested or delivered" (0.08). Both effective 2025-12-01. Which SKU a given Direct PUT stream bills under is NOT determinable from the API. The 5 KB rounding rule is NOT IN API. |
| CloudFront HTTPS requests, US | $0.01 per 10,000 ($0.000001 each) | AmazonCloudFront \| usagetype=US-Requests-Tier2-HTTPS \| global (no region) \| SKU NPFD6SEH9MXS8M4J \| "$0.0100 per 10,000 HTTPS Requests" |
| CloudFront data transfer out, US edge, first tier | $0.085/GB (first 10 TB); $0.080 next 40 TB | AmazonCloudFront \| usagetype=US-DataTransfer-Out-Bytes \| global \| SKU GV2WFGX37Q9PDSHF \| "$0.085 per GB - first 10 TB / month data transfer out". The always-free 1 TB / 10M requests is NOT IN API (tier starts at 0 and is $0.085). |
| CloudFront Functions | first 2,000,000 executions $0; then $0.10 per 1M | AmazonCloudFront \| usagetype=Executions-CloudFrontFunctions \| global \| SKU QAZUUEJG8GARJCET \| "$0.10 per 1,000,000 CloudFront Function Executions" |
| WAF web ACL | $5.00 per ACL-month (prorated hourly) | awswaf \| usagetype=USE1-WebACLV2 \| us-east-1 \| SKU KF2QAJUBXF7XNYSM \| "$5.00 per web ACL created (prorated hourly)" |
| WAF rule | $1.00 per rule-month (prorated hourly) | awswaf \| usagetype=USE1-RuleV2 \| us-east-1 \| SKU JGH3VFMTQFNJUV5W \| "$1.00 per rule created (prorated hourly)" |
| WAF requests | $0.60 per 1M | awswaf \| usagetype=USE1-RequestV2-Tier0 / Tier1 \| us-east-1 \| SKU 3T4KMURJGZDP3439 / 94S3KGQ8C7XGQFSJ \| "$0.60 per million requests processed" |
| ALB hourly | $0.0225 per ALB-hour (or partial hour) | AWSELB \| productFamily=Load Balancer-Application, usagetype=LoadBalancerUsage \| us-east-1 \| SKU 37CUWUT8GSNQEPUV \| "$0.0225 per Application LoadBalancer-hour (or partial hour)" |
| ALB LCU | $0.008 per LCU-hour | AWSELB \| usagetype=LCUUsage \| us-east-1 \| SKU P2XGEJ8N3KU52WA8 \| "$0.008 per used Application load balancer capacity unit-hour (or partial hour)" |
| Fargate Linux x86 | $0.04048/vCPU-h; $0.004445/GB-h | AmazonECS \| usagetype=USE1-Fargate-vCPU-Hours:perCPU / USE1-Fargate-GB-Hours \| us-east-1 \| SKU 8CESGAFWKAJ98PME / PBZNQUSEXZUC34C9 \| "AWS Fargate - vCPU - US East (N.Virginia)" / "AWS Fargate - Memory - US East (N.Virginia)" |
| Fargate Linux ARM | $0.03238/vCPU-h; $0.00356/GB-h | AmazonECS \| usagetype=USE1-Fargate-ARM-vCPU-Hours:perCPU / USE1-Fargate-ARM-GB-Hours \| us-east-1 \| SKU XSZATS4VYMDC9CYN / UNH9KPQP7W7C66C9 \| "AWS Fargate - ARM - vCPU - US East (N. Virginia)" / "AWS Fargate - ARM - Memory - US East (N. Virginia)" |
| Public IPv4 | $0.005 per address-hour, in-use and idle | AmazonVPC \| usagetype=USE1-PublicIPv4:InUseAddress / IdleAddress \| us-east-1 \| SKU 4GQUNXTFWVSGPUZK / T6YDQKTMVWKNJFJ8 \| "$0.005 per In-use public IPv4 address per hour" |
| NAT gateway hourly | $0.045/h (zonal). Regional NAT gateway also $0.045/h | AmazonEC2 \| productFamily=NAT Gateway, usagetype=NatGateway-Hours \| us-east-1 \| SKU M2YSHUBETB3JX4M4 \| "$0.045 per NAT Gateway Hour"; RegionalNatGateway-Hours SKU KVHMMSJX774M3XRN |
| NAT gateway data | $0.045 per GB processed | AmazonEC2 \| usagetype=NatGateway-Bytes \| us-east-1 \| SKU 59S5R83GFPUAGVR5 \| "$0.045 per GB Data Processed by NAT Gateways" |
| VPC interface endpoint hourly | $0.01 per endpoint-hour (one AZ ENI) | AmazonVPC \| usagetype=USE1-VpcEndpoint-Hours \| us-east-1 \| SKU EN2N5TATXE673A3B \| "$0.01 per VPC Endpoint Hour" |
| VPC interface endpoint data | $0.01/GB up to 1 PB | AmazonVPC \| usagetype=USE1-VpcEndpoint-Bytes \| us-east-1 \| SKU DQYYEZBCWSW5XS2R \| "$0.01 per GB for upto 1 PB monthly data processed by VPC Endpoints" |
| Lightsail container Nano | $0.0094086020/h = $7.00 at 744 h | AmazonLightsail \| usagetype=USE1-ContainerSvcUsage:Nano-0.25CPU-0.5GB \| us-east-1 \| SKU TVRJUC9D5VVSWH8Q \| "$0.0094 / Hour for Container Service Node of Power-Nano(0.25CPU-0.5GB)" |
| Lightsail container Micro | $0.0134408600/h = $10.00 at 744 h | same, usagetype=USE1-ContainerSvcUsage:Micro-0.25CPU-1GB \| SKU BVZXMH7F4UF2SP8B |
| Lightsail container Small | $0.0201612900/h = $15.00 at 744 h | same, usagetype=USE1-ContainerSvcUsage:Small-0.5CPU-1GB \| SKU 64ZSEA597RH57QZY |
| Lightsail Micro "Free" SKU | first 750 h $0.00, then $0.0134/h. Eligibility terms NOT IN API. | usagetype=USE1-ContainerSvcUsage:Micro-0.25CPU-1GB-Free \| SKU D5MZDUQZCJE8NHT7 |
| ECR storage | $0.10 per GB-Mo | AmazonECR \| usagetype=TimedStorage-ByteHrs \| us-east-1 \| SKU KJC988R4J65BDMTQ \| "$0.10 per GB-month of data storage" |
| CloudWatch Logs ingestion (Standard class) | $0.50 per GB | AmazonCloudWatch \| usagetype=USE1-DataProcessing-Bytes, operation=PutLogEvents \| us-east-1 \| SKU S8QGXX5R2BKKMDSJ \| "$0.50 per GB custom log data ingested in Standard log class" |
| CloudWatch Logs storage | $0.03 per GB-Mo | AmazonCloudWatch \| usagetype=USE1-TimedStorage-ByteHrs \| us-east-1 \| SKU 6K9ADYQAHV5KX9KZ \| "$0.03 per GB-mo of log storage" |
| App Runner provisioned memory | $0.007 per GB-h | AWSAppRunner \| usagetype=USE1-AppRunner-Provisioned-GB-hours \| us-east-1 \| SKU YYWUT3AQDJMRWWGA \| "AWS App Runner - Provisioned - GB-hours - US East (N. Virginia)" |
| App Runner active vCPU | $0.064 per vCPU-h | AWSAppRunner \| usagetype=USE1-AppRunner-vCPU-hours \| us-east-1 \| SKU 8FZ3ANRH34DG5WJ2 \| "AWS App Runner - vCPU - US East (N. Virginia)" |
| App Runner active memory | $0.007 per GB-h | AWSAppRunner \| usagetype=USE1-AppRunner-GB-hours \| us-east-1 \| SKU DH9DXBVSTZFG449B \| "AWS App Runner - GB-hours - US East (N. Virginia)" |
| App Runner automatic deployment | $1.00 per pipeline (per month, unit "pipelines") | AWSAppRunner \| usagetype=USE1-AppRunner-AutomaticDeployment \| SKU GAPMZ4VJNXNWKVJS |
| App Runner build | $0.005 per build-minute | AWSAppRunner \| usagetype=USE1-AppRunner-Build-mins \| SKU HVVA7M22NCWEH496 |

Not found / not obtainable: free-tier allowances (Lambda, API Gateway, CloudFront 1 TB/10M, S3) are not represented in the Price List API. Firehose dynamic-partitioning price was not re-queried (not needed for the options costed). Minimum App Runner instance size and whether App Runner can scale below 1 provisioned instance are not Price List facts.

## 2. Diff against the earlier lower-trust files

Verdict key: CONFIRMED (matches), NEW (was UNVERIFIED or missing, now has a value), WRONG (old value differs materially), MINOR (immaterial difference).

No earlier price was materially WRONG. The differences are below.

### 01-compute-hosting.md
- Lambda requests $0.20/M: CONFIRMED.
- Lambda x86 $0.0000166667/GB-s: CONFIRMED, but it is only Tier 1 (first 6B GB-s). NEW: tiers 2 and 3 are $0.0000150000 and $0.0000133334. Irrelevant at this volume. NEW: ARM is $0.0000133334 Tier 1 (not in 01).
- Lambda free tier (1M requests, 400,000 GB-s): still UNVERIFIED (NOT IN API).
- HTTP API $1.00/M, region "UNVERIFIED": now CONFIRMED for us-east-1 (first 300M).
- WAF $0.60/M, $5/ACL, $1/rule: CONFIRMED. "+$7 for existing ACL with 2 managed rule groups" is correct arithmetic ($5 + 2 x $1) assuming those groups count as 2 rules and carry no extra fee (managed-group fees NOT checked).
- CloudFront pay-as-you-go "not captured": NEW. HTTPS $0.01/10k (US); DTO first 10 TB $0.085/GB (US); Functions $0.10/M after first 2M free.
- App Runner provisioned memory $0.007/GB-h, active $0.064/vCPU-h + $0.007/GB-h: CONFIRMED. NEW: automatic deployment $1/pipeline, build $0.005/min (were "amounts not captured").
- App Runner idle ~$2.56/mo at 0.5 GB: arithmetic CONFIRMED ($0.007 x 0.5 x 730 = $2.555). The 0.5 GB size is an assumption (not a Price List fact).

### 02-results-storage.md
- DynamoDB write $0.625/M, read $0.125/M, storage $0.25/GB-Mo with 25 GB free, PITR $0.20/GB-Mo, export $0.10/GB: all CONFIRMED (us-east-1).
- S3 GET $0.0004/1,000: CONFIRMED (API says $0.004 per 10,000).
- S3 PUT "UNVERIFIED": NEW, $0.005 per 1,000. S3 storage "UNVERIFIED": NEW, $0.023/GB-Mo first 50 TB.
- Athena $5/TB, region "UNVERIFIED": CONFIRMED for us-east-1. The "10 MB minimum not confirmed for S3 queries": the SKU description says "minimum 10MB for each successful or cancelled queries" (CONFIRMED for the Athena SKU; the SKU is not split by data source).
- Firehose $0.029/GB, region "UNVERIFIED": us-east-1 $0.029/GB Tier 1 CONFIRMED. DIFFERENCE: a second Direct PUT SKU ("no-rounding") lists $0.08/GB, both effective 2025-12-01. 02's 5 KB rounding note is NOT IN API. At 1,000 small records the cost is under $0.001 either way, so immaterial, but the per-GB rate may be $0.08 instead of $0.029.
- S3 PUT cost for 1,000 objects: now 1,000 x $0.000005 = $0.005 (02 said "well under $0.01", which holds, but it is the largest line in the S3 option).

### 05-container-platforms.md
- ALB $0.0225/h and $0.008/LCU-h: CONFIRMED.
- Fargate x86 vCPU-h $0.04048: CONFIRMED. GB-h: 05 $0.004446 vs API $0.004445, MINOR (~0.02%).
- Fargate ARM vCPU-h and GB-h (05 per-second $0.0000089944 / $0.0000009889 = $0.032380 / $0.003560 per hour): CONFIRMED.
- Public IPv4 $0.005/h: CONFIRMED.
- NAT gateway "Ohio example only, UNVERIFIED for us-east-1": CONFIRMED. us-east-1 is $0.045/h and $0.045/GB. $32.85/mo hourly floor stands ($0.045 x 730).
- Interface endpoint "not researched": NEW, $0.01/endpoint-hour ($7.30/mo each in one AZ), $0.01/GB.
- ECR storage and CloudWatch Logs "not priced": NEW, $0.10/GB-Mo; $0.50/GB ingest, $0.03/GB-Mo stored.
- Lightsail Nano $7, Micro $10, Small $15: CONFIRMED (hourly price x 744 h = exactly $7.00/$10.00/$15.00). NEW: a "Micro (Free)" SKU gives the first 750 h at $0 (05 said "No container free trial stated on the page"). Eligibility is not in the API.
- 05's component totals ($9.01, $7.21, $36.04, $16.43, $5.84 upper bound, $3.65, $7.30, $29 to $36): arithmetic CONFIRMED against API rates. The ALB internet-facing "2 public IPv4" count is still an assumption (not a Price List fact); the internal ALB "no public IPv4" is still an inference.

## 3. Recomputed monthly cost, ~3,000 requests / ~1,000 responses

Assumptions (mine, not Price List facts): 730 h/month for hourly resources (Lightsail billed at its 744 h cap); 3,000 total HTTP requests of which 1,000 are submit POSTs; Lambda 256 MB, 100 ms per invocation (3,000 x 0.25 GB x 0.1 s = 75 GB-s); ~10 KB per response so 30 MB (0.03 GB) CloudFront data out; DynamoDB 1,000 writes (1 WRU each) and 1,000 reads (1 RRU each), ~1 MB stored (inside 25 GB free); free tiers ignored (list price); the existing CloudFront web ACL is shared, so no new ACL fee. CloudFront Functions assumed not used (2M/month free anyway). Data transfer between AWS services in region, Route 53 and ACM are excluded.

### A. Lambda Function URL + CloudFront OAC
| Line | Arithmetic | $ |
|---|---|---|
| Lambda requests | 3,000 x $0.0000002 | 0.0006 |
| Lambda GB-s x86 | 75 x $0.0000166667 | 0.00125 |
| CloudFront HTTPS | 3,000 x $0.000001 | 0.0030 |
| CloudFront data out | 0.03 GB x $0.085 | 0.00255 |
| WAF requests (shared ACL) | 3,000 x $0.0000006 | 0.0018 |
| DynamoDB writes | 1,000 x $0.000000625 | 0.000625 |
| DynamoDB reads | 1,000 x $0.000000125 | 0.000125 |
| Total (list price) | | about $0.010 |
- ARM instead of x86: GB-s line 75 x $0.0000133334 = $0.0010 (saves $0.00025).
- Dedicated new ACL instead of shared: + $5 + 2 rules x $1 = + $7.00, total about $7.01.
- With real free tiers (Lambda 1M requests, CloudFront 1 TB/10M requests; both NOT IN API), the variable cost would round to about $0.

### B. HTTP API + Lambda + CloudFront
Same as A, plus HTTP API 3,000 x $0.000001 = $0.003. Total about $0.013. WAF stays on CloudFront (HTTP API cannot take WAF, per 01). Dedicated ACL: about $7.01 + 0.003.

### C. ECS Fargate + ALB, public subnet, no NAT, smallest task (0.25 vCPU / 0.5 GB, 1 task always on)
| Line | Arithmetic | $ |
|---|---|---|
| ALB hourly | 730 x $0.0225 | 16.425 |
| ALB LCU | at ~3,000 requests/month well under 1 LCU; billed fraction not determinable. Bounds: $0 to 1 LCU x 730 x $0.008 = $5.84 | about 0 (upper bound 5.84) |
| Fargate x86 | (0.25 x $0.04048 + 0.5 x $0.004445) x 730 = $0.0123425 x 730 | 9.010 |
| Task public IPv4 | 730 x $0.005 | 3.650 |
| ECR (assume 0.1 GB image) | 0.1 x $0.10 | 0.010 |
| CloudWatch Logs (assume 3 MB) | 0.003 GB x $0.50 | 0.0015 |
| DynamoDB | as A | 0.0007 |
| **Internal ALB total** (no ALB public IPv4) | 16.425 + 9.010 + 3.650 + 0.012 | **about $29.10** |
| ALB public IPv4, internet-facing, 2 AZs (assumed 1 address per AZ) | 2 x 730 x $0.005 | + 7.300 |
| **Internet-facing ALB total** | 29.10 + 7.30 | **about $36.40** |
- ARM task: (0.25 x $0.03238 + 0.5 x $0.00356) x 730 = $0.009875 x 730 = $7.209. Totals: internal about $27.30, internet-facing about $34.60.
- Upper bound with 1 full LCU all month: add $5.84.
- Internal ALB behind CloudFront (VPC origin) adds the A-style CloudFront/WAF lines, about $0.0074 plus shared ACL. Internal ALB with a public-subnet task still pays the task IPv4 ($3.65).
- If the task sits in a private subnet instead: NAT gateway $0.045 x 730 = $32.85/month plus $0.045/GB; or ECR/logs interface endpoints at $0.01 x 730 = $7.30 each per AZ (ecr.api + ecr.dkr + logs = 3 x $7.30 = $21.90 for one AZ, S3 gateway endpoint assumed free; endpoint set needed is from 05's doc references, not re-verified).
- Express default size (1 vCPU / 2 GB x86): ($0.04048 + 2 x $0.004445) x 730 = $36.04 for the task alone; totals about $56 (internal) / $63 (internet-facing).

### D. Lightsail container Nano
- $0.0094086020 x 744 h = $7.00 per month (fixed, whether used or not). Micro $10.00, Small $15.00.
- Transfer: 500 GB/month included per 05 (public docs, not re-verified in API); 0.03 GB used.
- DynamoDB as A: $0.0007. Total about $7.00.
- Micro free SKU: first 750 h at $0, so a Micro could be $0 for its first month if eligible (terms NOT IN API), then $10.00.
- Lightsail has no ACM-cert reuse and no WAF per 05; any CloudFront in front would add A-style CloudFront lines (about $0.007).

### E. App Runner idle (smallest assumed 0.25 vCPU / 0.5 GB)
| Line | Arithmetic | $ |
|---|---|---|
| Provisioned memory (always on) | 0.5 GB x 730 x $0.007 | 2.555 |
| Active compute, if active 10 h/month (illustrative) | 10 x (0.25 x $0.064 + 0.5 x $0.007) = 10 x $0.0195 | 0.195 |
| Automatic deployment pipeline (optional) | 1 x $1.00 | 1.00 |
| Idle total (no pipeline) | | about $2.56 |
| With 10 active hours and pipeline | | about $3.75 |
- At 1 GB provisioned: 1 x 730 x $0.007 = $5.11 idle.
- App Runner is closed to new customers (01, docs finding); not a Price List fact.
