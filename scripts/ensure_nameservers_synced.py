#!/usr/bin/env python3
"""Ensure Route53 hosted zone and domain registrar name servers are synced.

Purpose:
- Verify Route53 hosted zone name servers match domain registrar name servers
- If they don't match, update the domain registrar to match the hosted zone
- Idempotent - safe to run multiple times
- Works only with Route53 Domains (not external registrars)

Usage:
    python scripts/ensure_nameservers_synced.py <environment> [options]

Examples:
    # Check and fix if needed
    python scripts/ensure_nameservers_synced.py production

    # Just check, don't fix
    python scripts/ensure_nameservers_synced.py production --check-only

    # Preview what would be done
    python scripts/ensure_nameservers_synced.py production --dry-run

    # Wait for DNS propagation after sync
    python scripts/ensure_nameservers_synced.py production --wait-for-propagation

Requirements:
- Domain must be registered with Route53 Domains
- AWS credentials with permissions for:
  - route53:GetHostedZone
  - route53domains:GetDomainDetail
  - route53domains:UpdateDomainNameservers
  - route53domains:GetOperationDetail
  - cloudformation:DescribeStackResources
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

import boto3
from botocore.exceptions import ClientError

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}{text}{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}\n")


def print_section(text: str):
    """Print a formatted section header."""
    print(f"\n{BLUE}▶ {text}{RESET}")
    print("-" * 70)


def print_success(text: str):
    """Print a success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"{RED}✗{RESET} {text}")


def print_info(text: str):
    """Print an info message."""
    print(f"{BLUE}ℹ{RESET} {text}")


def get_domain_from_config(environment: str) -> str:
    """Get domain name from environment config file.

    Args:
        environment: Environment name (e.g., 'production')

    Returns:
        Domain name from config (e.g., 'natenite.net')

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid or missing domain
    """
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "config" / environment / "environment.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            f"Valid environments: dev, staging, production"
        )

    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)

    domain = config.get("default_fqdn")
    if not domain:
        raise ValueError(
            f"Missing 'default_fqdn' in config file: {config_path}"
        )

    return domain


def find_registrar_hosted_zone(
    domain_name: str,
) -> Tuple[str, str, List[str]]:
    """Find hosted zone created by Route53 Registrar for the domain.

    Searches for a hosted zone matching the domain name with the description
    'HostedZone created by Route53 Registrar', which identifies the zone
    automatically created when registering a domain with Route53.

    Args:
        domain_name: The domain name to search for (e.g., 'natenite.net')

    Returns:
        Tuple of (zone_id, domain_name, nameservers)

    Raises:
        ValueError: If no matching hosted zone is found
    """
    r53_client = boto3.client("route53")

    # List all hosted zones and find the one with registrar description
    paginator = r53_client.get_paginator("list_hosted_zones")
    target_zone_name = f"{domain_name}."

    for page in paginator.paginate():
        for zone in page["HostedZones"]:
            if zone["Name"] == target_zone_name:
                # Get detailed zone info to check the description
                zone_id = zone["Id"].split("/")[-1]
                zone_response = r53_client.get_hosted_zone(Id=zone_id)

                # Check if this is the registrar-created zone
                zone_config = zone_response.get("HostedZone", {}).get(
                    "Config", {}
                )
                comment = zone_config.get("Comment", "")

                if comment == "HostedZone created by Route53 Registrar":
                    nameservers = zone_response["DelegationSet"][
                        "NameServers"
                    ]
                    return zone_id, domain_name, nameservers

    # If we get here, no matching zone was found
    raise ValueError(
        f"No hosted zone found for {domain_name} with description "
        "'HostedZone created by Route53 Registrar'. "
        "Ensure the domain is registered with Route53 Domains."
    )


def check_domain_with_route53(domains_client, domain_name: str) -> bool:
    """Check if domain is registered with Route53 Domains."""
    try:
        domains_client.get_domain_detail(DomainName=domain_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidInput":
            return False
        raise


def get_domain_nameservers(domains_client, domain_name: str) -> List[str]:
    """Get current name servers configured for the domain."""
    response = domains_client.get_domain_detail(DomainName=domain_name)
    return sorted([ns["Name"] for ns in response["Nameservers"]])


def nameservers_match(ns1: List[str], ns2: List[str]) -> bool:
    """Check if two name server lists match (ignoring order)."""
    return set(ns1) == set(ns2)


def update_domain_nameservers(
    domains_client, domain_name: str, nameservers: List[str], dry_run: bool
) -> str:
    """Update domain name servers and return operation ID.

    Returns empty string if dry_run is True.
    """
    if dry_run:
        print_warning("DRY RUN: Would update domain name servers")
        return ""

    ns_list = [{"Name": ns} for ns in nameservers]
    response = domains_client.update_domain_nameservers(
        DomainName=domain_name, Nameservers=ns_list
    )
    return response["OperationId"]


def wait_for_operation(
    domains_client, operation_id: str, timeout: int = 300
) -> bool:
    """Wait for Route53 Domains operation to complete."""
    if not operation_id:
        return True

    print_info("Waiting for Route53 Domains operation to complete...")
    start_time = time.time()
    dots = 0

    while time.time() - start_time < timeout:
        response = domains_client.get_operation_detail(OperationId=operation_id)
        status = response["Status"]

        if status == "SUCCESSFUL":
            print()  # New line after dots
            print_success("Operation completed successfully")
            return True

        if status == "FAILED":
            print()
            message = response.get("Message", "Unknown error")
            raise RuntimeError(f"Operation failed: {message}")

        if status == "ERROR":
            print()
            raise RuntimeError("Operation encountered an error")

        # Show progress dots
        print(".", end="", flush=True)
        dots += 1
        if dots % 50 == 0:
            print()  # New line every 50 dots
        time.sleep(5)

    print()
    raise TimeoutError("Operation timed out after 5 minutes")


def check_dns_propagation(domain_name: str, expected_ns: List[str]) -> bool:
    """Check if DNS has propagated by querying public DNS servers."""
    import subprocess

    print_section("Checking DNS Propagation")

    # Try a few public DNS servers
    dns_servers = [
        ("Google DNS", "8.8.8.8"),
        ("Cloudflare DNS", "1.1.1.1"),
        ("Quad9 DNS", "9.9.9.9"),
    ]

    all_match = True
    expected_set = set(expected_ns)

    for name, server in dns_servers:
        try:
            result = subprocess.run(
                ["dig", f"@{server}", "NS", domain_name, "+short"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                actual_ns = set(
                    line.rstrip(".") for line in result.stdout.strip().split("\n") if line
                )
                if actual_ns == expected_set:
                    print_success(f"{name} ({server}): Propagated")
                else:
                    print_warning(f"{name} ({server}): Not yet propagated")
                    all_match = False
            else:
                print_warning(f"{name} ({server}): Query failed")
                all_match = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print_warning(f"{name} ({server}): Could not query")
            all_match = False

    return all_match


def main():  # pylint: disable=too-many-statements,too-many-branches,too-many-locals
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Ensure Route53 hosted zone and domain registrar name servers match",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check and fix if needed (default)
  python %(prog)s production

  # Just check status, don't make changes
  python %(prog)s production --check-only

  # Preview what would be done
  python %(prog)s production --dry-run

  # Fix and wait for DNS propagation
  python %(prog)s production --wait-for-propagation
        """,
    )
    parser.add_argument(
        "environment",
        type=str,
        help="Environment (e.g., production, staging, dev)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check if name servers match, don't fix",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--wait-for-propagation",
        action="store_true",
        help="Wait and check for DNS propagation after sync",
    )
    args = parser.parse_args()

    print_header("Route53 Name Server Synchronization")
    print(f"Environment: {args.environment}")
    if args.check_only:
        print(f"Mode: {BLUE}CHECK ONLY{RESET}")
    elif args.dry_run:
        print(f"Mode: {YELLOW}DRY RUN{RESET}")
    print()

    # Initialize AWS clients
    domains_client = boto3.client("route53domains", region_name="us-east-1")

    try:
        # Step 1: Get domain name from config
        print_section("Step 1: Getting Domain from Configuration")
        domain_name = get_domain_from_config(args.environment)
        print_success(f"Domain: {domain_name}")

        # Step 2: Find hosted zone created by Route53 Registrar
        print_section(
            "Step 2: Finding Hosted Zone Created by Route53 Registrar"
        )
        print_info(
            "Searching for hosted zone with description: "
            "'HostedZone created by Route53 Registrar'"
        )

        zone_id, domain_name, hz_nameservers = find_registrar_hosted_zone(
            domain_name
        )

        print_success(f"Hosted Zone ID: {zone_id}")
        print_success("Hosted Zone Name Servers:")
        for ns in sorted(hz_nameservers):
            print(f"  • {ns}")

        # Step 3: Check if domain is with Route53
        print_section("Step 3: Checking Domain Registration")
        if not check_domain_with_route53(domains_client, domain_name):
            print_error("Domain is NOT registered with Route53 Domains")
            print()
            print_header("Manual Action Required")
            print(
                f"The domain '{domain_name}' is registered with an "
                "external registrar."
            )
            print("\nYou must manually configure these name servers at your registrar:")
            for ns in sorted(hz_nameservers):
                print(f"  • {ns}")
            print("\nSee DOMAIN_AUTOMATION.md for detailed instructions.")
            return 1

        print_success("Domain is registered with Route53 Domains")

        # Step 4: Get domain name servers
        print_section("Step 4: Getting Domain Registrar Name Servers")
        domain_nameservers = get_domain_nameservers(domains_client, domain_name)
        print_success("Domain Registrar Name Servers:")
        for ns in domain_nameservers:
            print(f"  • {ns}")

        # Step 5: Compare name servers
        print_section("Step 5: Comparing Name Servers")
        if nameservers_match(hz_nameservers, domain_nameservers):
            print_success(
                "Name servers MATCH! Hosted zone and domain registrar are in sync."
            )
            print()
            print_header("✓ Success: Already Synchronized")
            print("No action needed. Name servers are correctly configured.")

            # Optionally check DNS propagation
            if args.wait_for_propagation:
                check_dns_propagation(domain_name, hz_nameservers)

            return 0

        # Name servers don't match
        print_warning("Name servers DO NOT MATCH")
        print()

        # Show differences
        hz_set = set(hz_nameservers)
        domain_set = set(domain_nameservers)

        if hz_set - domain_set:
            print(f"{GREEN}Name servers in Hosted Zone but not in Domain:{RESET}")
            for ns in sorted(hz_set - domain_set):
                print(f"  + {ns}")

        if domain_set - hz_set:
            print(f"{RED}Name servers in Domain but not in Hosted Zone:{RESET}")
            for ns in sorted(domain_set - hz_set):
                print(f"  - {ns}")

        # Step 6: Fix the mismatch (unless check-only)
        if args.check_only:
            print()
            print_header("⚠ Check Complete: Name Servers Out of Sync")
            print(
                "Run without --check-only to update domain registrar "
                "to match hosted zone."
            )
            return 1

        print_section("Step 6: Updating Domain Registrar Name Servers")
        print_info("Updating domain registrar to match hosted zone...")

        operation_id = update_domain_nameservers(
            domains_client, domain_name, hz_nameservers, args.dry_run
        )

        if args.dry_run:
            print()
            print_header("✓ Dry Run Complete")
            print("Run without --dry-run to apply these changes.")
            return 0

        if operation_id:
            print_success(f"Update initiated (Operation ID: {operation_id})")

            # Wait for operation
            wait_for_operation(domains_client, operation_id)

            # Verify the update
            print_section("Step 7: Verifying Update")
            updated_ns = get_domain_nameservers(domains_client, domain_name)

            if nameservers_match(hz_nameservers, updated_ns):
                print_success("Verification passed: Name servers now match!")
            else:
                print_error("Verification failed: Name servers still don't match")
                return 1

        # Optionally check DNS propagation
        if args.wait_for_propagation:
            print()
            print_info("Waiting 30 seconds before checking DNS propagation...")
            time.sleep(30)
            propagated = check_dns_propagation(domain_name, hz_nameservers)

            if not propagated:
                print()
                print_warning(
                    "DNS has not fully propagated yet. "
                    "This can take up to 48 hours."
                )

        # Success!
        print()
        print_header("✓ Success: Name Servers Synchronized")
        print("Domain registrar name servers now match the hosted zone.")
        print()
        print("Next steps:")
        print("  1. DNS propagation may take up to 48 hours")
        print("  2. ACM will automatically validate the certificate")
        print("  3. Run verify_certificate_setup.sh to check certificate status")

        return 0

    except (ValueError, RuntimeError, TimeoutError, ClientError) as e:
        print()
        print_error(f"Error: {str(e)}")
        print()
        print_header("✗ Failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
