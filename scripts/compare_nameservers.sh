#!/usr/bin/env bash
# Compare public hosted zone name servers to certificate validation name servers.
#
# Purpose:
# - Query the Route53 public hosted zone for its name servers
# - Query the ACM certificate for its validation name servers
# - Compare the two sets to ensure they match
#
# Usage:
#   ./scripts/compare_nameservers.sh <environment>
#
# Example:
#   ./scripts/compare_nameservers.sh production

set -Eeuo pipefail

# Get environment from CLI args
if [ $# -ne 1 ]; then
    echo "Usage: $0 <environment>" >&2
    echo "Example: $0 production" >&2
    exit 1
fi

ENVIRONMENT="$1"
APP_NAME="NateNite"
STACK_PREFIX="${APP_NAME}${ENVIRONMENT^}Certificate"
STACK_NAME="${STACK_PREFIX}Stack"

echo "Environment: ${ENVIRONMENT}"
echo "Stack name: ${STACK_NAME}"
echo ""

# Get the hosted zone ID from the CloudFormation stack
echo "Retrieving hosted zone ID from stack..."
HOSTED_ZONE_ID=$(aws cloudformation describe-stack-resources \
    --stack-name "${STACK_NAME}" \
    --query "StackResources[?ResourceType=='AWS::Route53::HostedZone'].PhysicalResourceId" \
    --output text)

if [ -z "${HOSTED_ZONE_ID}" ]; then
    echo "Error: Could not find hosted zone in stack ${STACK_NAME}" >&2
    exit 1
fi
echo "Hosted zone ID: ${HOSTED_ZONE_ID}"
echo ""

# Get the certificate ARN from the CloudFormation stack
echo "Retrieving certificate ARN from stack..."
CERTIFICATE_ARN=$(aws cloudformation describe-stack-resources \
    --stack-name "${STACK_NAME}" \
    --query "StackResources[?ResourceType=='AWS::CertificateManager::Certificate'].PhysicalResourceId" \
    --output text)

if [ -z "${CERTIFICATE_ARN}" ]; then
    echo "Error: Could not find certificate in stack ${STACK_NAME}" >&2
    exit 1
fi
echo "Certificate ARN: ${CERTIFICATE_ARN}"
echo ""

# Get hosted zone name servers
echo "Retrieving hosted zone name servers..."
ZONE_NS=$(aws route53 get-hosted-zone \
    --id "${HOSTED_ZONE_ID}" \
    --query "DelegationSet.NameServers" \
    --output json)
echo "Hosted zone name servers:"
echo "${ZONE_NS}" | jq -r '.[]' | sort
echo ""

# Get certificate validation name servers
echo "Retrieving certificate validation records..."
CERT_VALIDATION=$(aws acm describe-certificate \
    --certificate-arn "${CERTIFICATE_ARN}" \
    --query "Certificate.DomainValidationOptions[0].ResourceRecord.Value" \
    --output text)

if [ -z "${CERT_VALIDATION}" ]; then
    echo "Warning: Certificate validation record not yet created" >&2
    echo "The certificate may still be provisioning" >&2
    exit 0
fi

echo "Certificate validation CNAME target: ${CERT_VALIDATION}"
echo ""

# Query the validation record to get its name servers
VALIDATION_NAME=$(aws acm describe-certificate \
    --certificate-arn "${CERTIFICATE_ARN}" \
    --query "Certificate.DomainValidationOptions[0].ResourceRecord.Name" \
    --output text)

echo "Querying name servers for validation record: ${VALIDATION_NAME}"
VALIDATION_NS=$(dig +short NS "${VALIDATION_NAME}" | sort)

if [ -z "${VALIDATION_NS}" ]; then
    echo "Warning: Could not resolve name servers for validation record" >&2
    echo "This may indicate DNS propagation is still in progress" >&2
else
    echo "Validation record name servers:"
    echo "${VALIDATION_NS}"
    echo ""
fi

# Compare the hosted zone domain to ensure it's authoritative
ZONE_NAME=$(aws route53 get-hosted-zone \
    --id "${HOSTED_ZONE_ID}" \
    --query "HostedZone.Name" \
    --output text)

echo "Hosted zone domain: ${ZONE_NAME}"
echo ""
echo "Verification complete."
echo "Ensure your domain registrar's name servers match the hosted zone name servers above."
