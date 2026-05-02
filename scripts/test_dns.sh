#!/usr/bin/env bash
# Test DNS resolution for natenite.net and www.natenite.net
#
# Purpose:
# - Check if apex domain resolves
# - Check if www subdomain resolves
# - Verify both point to CloudFront distribution
# - Test HTTPS connectivity
#
# Usage:
#   ./scripts/test_dns.sh <environment>
#
# Example:
#   ./scripts/test_dns.sh production

set -Eeuo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>" >&2
    echo "Example: $0 production" >&2
    exit 1
fi

ENVIRONMENT="$1"
APP_NAME="NateNite"
STACK_PREFIX="${APP_NAME}${ENVIRONMENT^}Site"
STACK_NAME="${STACK_PREFIX}Stack"

# ANSI color codes
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
BLUE="\033[94m"
RESET="\033[0m"

echo "=========================================="
echo "DNS Resolution Test"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo ""

# Get the domain from stack
echo "Step 1: Getting domain from stack..."
echo "--------------------------------------------------------"
CERT_STACK_NAME="${APP_NAME}${ENVIRONMENT^}CertificateStack"
HOSTED_ZONE_ID=$(aws cloudformation describe-stack-resources \
    --stack-name "${CERT_STACK_NAME}" \
    --query "StackResources[?ResourceType=='AWS::Route53::HostedZone'].PhysicalResourceId" \
    --output text)

if [ -z "${HOSTED_ZONE_ID}" ]; then
    echo -e "${RED}✗${RESET} Could not find hosted zone in stack ${CERT_STACK_NAME}"
    exit 1
fi

DOMAIN=$(aws route53 get-hosted-zone \
    --id "${HOSTED_ZONE_ID}" \
    --query "HostedZone.Name" \
    --output text | sed 's/\.$//')

echo -e "${GREEN}✓${RESET} Domain: ${DOMAIN}"
echo ""

# Get CloudFront distribution domain
echo "Step 2: Getting CloudFront distribution..."
echo "--------------------------------------------------------"
DISTRIBUTION_DOMAIN=$(aws cloudformation describe-stack-resources \
    --stack-name "${STACK_NAME}" \
    --query "StackResources[?ResourceType=='AWS::CloudFront::Distribution'].PhysicalResourceId" \
    --output text)

if [ -z "${DISTRIBUTION_DOMAIN}" ]; then
    echo -e "${RED}✗${RESET} Could not find CloudFront distribution in stack ${STACK_NAME}"
    exit 1
fi

# Get the actual CloudFront domain name
CF_DOMAIN_NAME=$(aws cloudfront get-distribution \
    --id "${DISTRIBUTION_DOMAIN}" \
    --query "Distribution.DomainName" \
    --output text)

echo -e "${GREEN}✓${RESET} CloudFront Distribution: ${DISTRIBUTION_DOMAIN}"
echo -e "${GREEN}✓${RESET} CloudFront Domain: ${CF_DOMAIN_NAME}"
echo ""

# Test DNS resolution for apex domain
echo "Step 3: Testing DNS resolution for ${DOMAIN}..."
echo "--------------------------------------------------------"
APEX_IP=$(dig +short "${DOMAIN}" | head -1)
if [ -n "${APEX_IP}" ]; then
    echo -e "${GREEN}✓${RESET} ${DOMAIN} resolves to: ${APEX_IP}"
else
    echo -e "${RED}✗${RESET} ${DOMAIN} does not resolve"
fi
echo ""

# Test DNS resolution for www
echo "Step 4: Testing DNS resolution for www.${DOMAIN}..."
echo "--------------------------------------------------------"
WWW_IP=$(dig +short "www.${DOMAIN}" | head -1)
if [ -n "${WWW_IP}" ]; then
    echo -e "${GREEN}✓${RESET} www.${DOMAIN} resolves to: ${WWW_IP}"
else
    echo -e "${RED}✗${RESET} www.${DOMAIN} does not resolve"
fi
echo ""

# Test HTTPS connectivity for apex
echo "Step 5: Testing HTTPS connectivity..."
echo "--------------------------------------------------------"
echo "Testing https://${DOMAIN}..."
if curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${DOMAIN}" | grep -q "^[23]"; then
    echo -e "${GREEN}✓${RESET} https://${DOMAIN} is accessible"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${DOMAIN}" || echo "000")
    if [ "${HTTP_CODE}" = "000" ]; then
        echo -e "${YELLOW}⚠${RESET} https://${DOMAIN} connection failed (still propagating?)"
    else
        echo -e "${YELLOW}⚠${RESET} https://${DOMAIN} returned HTTP ${HTTP_CODE}"
    fi
fi

echo ""
echo "Testing https://www.${DOMAIN}..."
if curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://www.${DOMAIN}" | grep -q "^[23]"; then
    echo -e "${GREEN}✓${RESET} https://www.${DOMAIN} is accessible"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://www.${DOMAIN}" || echo "000")
    if [ "${HTTP_CODE}" = "000" ]; then
        echo -e "${YELLOW}⚠${RESET} https://www.${DOMAIN} connection failed (still propagating?)"
    else
        echo -e "${YELLOW}⚠${RESET} https://www.${DOMAIN} returned HTTP ${HTTP_CODE}"
    fi
fi

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
if [ -n "${APEX_IP}" ] && [ -n "${WWW_IP}" ]; then
    echo -e "${GREEN}✓${RESET} DNS is configured correctly"
    echo ""
    echo "Your site should be accessible at:"
    echo "  - https://${DOMAIN}"
    echo "  - https://www.${DOMAIN}"
else
    echo -e "${YELLOW}⚠${RESET} DNS is not fully propagated yet"
    echo ""
    echo "Next steps:"
    echo "1. Wait 5-15 minutes for DNS propagation"
    echo "2. Run this script again to verify"
    echo "3. Check Route53 records in AWS Console"
fi
echo ""
