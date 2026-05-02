# Deployment Steps for natenite.net

## Current Situation

You have **two duplicate hosted zones** for natenite.net. You need to:
1. Keep the hosted zone that matches your domain registrar's name servers
2. Delete the duplicate zone
3. Redeploy the stacks to use the existing zone

## Step 1: Identify Which Hosted Zone to Keep

First, identify your domain registrar's name servers and which hosted zone matches them:

```bash
# List all hosted zones for natenite.net
aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='natenite.net.']" \
  --output table

# For each zone, get its name servers
aws route53 get-hosted-zone --id /hostedzone/ZONE_ID_1
aws route53 get-hosted-zone --id /hostedzone/ZONE_ID_2
```

**Check your domain registrar:**
- If registered with Route53 Domains:
  ```bash
  aws route53domains get-domain-detail \
    --domain-name natenite.net \
    --region us-east-1 \
    --query "Nameservers[*].Name"
  ```
- If registered with external registrar (GoDaddy, Namecheap, etc.):
  - Log into your registrar's control panel
  - Find the DNS/Name Server settings
  - Note which name servers are configured

**Decision:** Keep the hosted zone whose name servers **match** your registrar.

## Step 2: Delete the Duplicate Hosted Zone

Once you've identified which zone to delete:

```bash
# Delete the duplicate zone (use the ID of the one you DON'T want to keep)
aws route53 delete-hosted-zone --id /hostedzone/ZONE_ID_TO_DELETE
```

**Note:** You can only delete a zone if it has no records other than the default NS and SOA records. If the duplicate has other records, you may need to delete them first.

## Step 3: Verify CDK Context

The Certificate stack now uses `HostedZone.from_lookup()` which caches the zone ID in `cdk.context.json`. Clear the cache to ensure it finds the correct zone:

```bash
# Remove cached hosted zone lookups
rm -f cdk.context.json

# Or just clear the specific entry
# Edit cdk.context.json and remove the "hosted-zone:..." entry
```

## Step 4: Synthesize to Verify

Test that CDK can find your hosted zone:

```bash
cdk synth NateNiteProductionCertificateStack
```

This should succeed without errors. Check the output to ensure it's using the correct hosted zone.

## Step 5: Deploy the Stacks

Now deploy both stacks in order:

```bash
# Deploy Certificate stack first
cdk deploy NateNiteProductionCertificateStack

# Then deploy Site stack
cdk deploy NateNiteProductionSiteStack
```

The deployment will:
- Use the existing hosted zone (not create a new one)
- Create ACM certificate with DNS validation records for:
  - natenite.net
  - www.natenite.net
  - *.natenite.net (wildcard)
- Create S3 bucket for site content
- Create CloudFront distribution with WAF protection
- Create Route53 A records for:
  - natenite.net → CloudFront
  - www.natenite.net → CloudFront

## Step 6: Verify Name Servers Match

Ensure your registrar's name servers match the hosted zone:

```bash
# Check and optionally sync if using Route53 Domains
python scripts/ensure_nameservers_synced.py production --check-only

# If they don't match and you use Route53 Domains, sync them:
python scripts/ensure_nameservers_synced.py production

# Or if external registrar, manually update at your registrar
```

## Step 7: Wait for Certificate Validation

ACM will validate the certificate automatically via DNS:

```bash
# Check certificate status
./scripts/verify_certificate_setup.sh production
```

This typically takes 5-30 minutes. The certificate must be validated before CloudFront will work properly.

## Step 8: Test DNS Resolution

Once deployed, test that DNS is working:

```bash
# Test DNS resolution and HTTPS connectivity
./scripts/test_dns.sh production
```

This will verify:
- natenite.net resolves to CloudFront
- www.natenite.net resolves to CloudFront
- HTTPS is working for both domains

## Step 9: Upload Site Content

Once DNS is working, upload your Hugo static site content:

```bash
# Build your Hugo site
cd /path/to/your/hugo/site
hugo

# Sync to S3 bucket
aws s3 sync public/ s3://natenite-production-site-content/ --delete

# Invalidate CloudFront cache
DISTRIBUTION_ID=$(aws cloudformation describe-stack-resources \
  --stack-name NateNiteProductionSiteStack \
  --query "StackResources[?ResourceType=='AWS::CloudFront::Distribution'].PhysicalResourceId" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id "${DISTRIBUTION_ID}" \
  --paths "/*"
```

## Troubleshooting

### DNS Not Resolving

**Problem:** `dig natenite.net` returns no results

**Solutions:**
1. Check that Route53 A records exist:
   ```bash
   ZONE_ID=$(aws cloudformation describe-stack-resources \
     --stack-name NateNiteProductionCertificateStack \
     --query "StackResources[?ResourceType=='AWS::Route53::HostedZone'].PhysicalResourceId" \
     --output text)
   
   aws route53 list-resource-record-sets --hosted-zone-id "${ZONE_ID}"
   ```

2. Verify registrar name servers match hosted zone name servers

3. Wait for DNS propagation (can take up to 48 hours, usually 5-30 minutes)

### Certificate Pending Validation

**Problem:** Certificate stuck in PENDING_VALIDATION status

**Solutions:**
1. Verify validation CNAME records exist in Route53:
   ```bash
   ./scripts/verify_certificate_setup.sh production
   ```

2. Ensure name servers match between registrar and hosted zone

3. Wait for DNS propagation

### CloudFront Returns 403 Forbidden

**Problem:** https://natenite.net returns 403 error

**Solutions:**
1. Upload content to S3 bucket with an `index.html` file

2. Check S3 bucket policy allows CloudFront to access it

3. Verify CloudFront distribution status is "Deployed"

### Multiple Hosted Zones After Deploy

**Problem:** CDK created a new hosted zone instead of using existing one

**Solutions:**
1. Clear CDK context cache: `rm -f cdk.context.json`

2. Ensure you're deploying to the correct AWS account

3. Delete the new zone and redeploy

## Summary

After completing these steps, you should have:
- ✅ Single hosted zone for natenite.net
- ✅ ACM certificate validated for natenite.net, www.natenite.net, *.natenite.net
- ✅ CloudFront distribution with WAF protection
- ✅ Route53 A records pointing both domains to CloudFront
- ✅ S3 bucket for site content
- ✅ HTTPS working for both https://natenite.net and https://www.natenite.net
