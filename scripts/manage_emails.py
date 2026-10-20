#!/usr/bin/env python3
"""Find and delete the email addresses respondents left.

Purpose:
- Let the poll owner keep to a retention choice (purge old addresses) and
  honor a removal request (delete one address), without touching responses.

Usage:
- PYTHONPATH=. python3 scripts/manage_emails.py purge --older-than-days N
- PYTHONPATH=. python3 scripts/manage_emails.py delete --email ADDRESS
- Both only report what they would delete unless `--yes` is added.

Notes:
- Output lists record keys and dates, never the addresses themselves.
"""

import argparse
from datetime import datetime, timedelta, timezone

from dump_poll import open_table

EMAIL_PREFIX = "EMAIL#"


def _email_records(table):
    """Yield every email record, following the scan's result pages."""
    query = {
        "FilterExpression": "begins_with(sk, :prefix)",
        "ExpressionAttributeValues": {":prefix": EMAIL_PREFIX},
    }
    while True:
        page = table.scan(**query)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _without_address(record):
    """The parts of an email record that are safe to print."""
    return {
        "pk": record["pk"],
        "sk": record["sk"],
        "submittedAt": record["submittedAt"],
    }


def _delete(table, records):
    """Delete the given email records by key."""
    for record in records:
        table.delete_item(Key={"pk": record["pk"], "sk": record["sk"]})


def purge_older_than(table, days, now, apply=False):
    """Report (and with `apply`, delete) emails older than `days` days.

    A record exactly `days` days old is not older, so it stays.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days < 0:
        raise ValueError("days must be a whole number, zero or more")
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = [
        record
        for record in _email_records(table)
        if record["submittedAt"] < cutoff
    ]
    if apply:
        _delete(table, found)
    return [_without_address(record) for record in found]


def delete_by_email(table, address, apply=False):
    """Report (and with `apply`, delete) every record for one address.

    Matching ignores case and surrounding spaces, across all polls.
    """
    if not isinstance(address, str) or not address.strip():
        raise ValueError("an email address is required")
    wanted = address.strip().lower()
    found = [
        record
        for record in _email_records(table)
        if record["email"].strip().lower() == wanted
    ]
    if apply:
        _delete(table, found)
    return [_without_address(record) for record in found]


def _report(found, apply):
    """Print what was found (keys and dates only) and what happened."""
    for record in found:
        print(f"{record['pk']}  {record['sk']}  {record['submittedAt']}")
    if apply:
        print(f"Deleted {len(found)} record(s).")
    else:
        print(f"Dry run: {len(found)} record(s) would be deleted. Add --yes.")


def main(argv=None, table=None, now=None):
    """Run the purge or delete command; `table` and `now` can be injected."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app-env", default="production")
    commands = parser.add_subparsers(dest="command", required=True)
    purge = commands.add_parser(
        "purge", help="delete emails older than N days"
    )
    purge.add_argument("--older-than-days", type=int, required=True)
    delete = commands.add_parser("delete", help="delete one address")
    delete.add_argument("--email", required=True)
    for command in (purge, delete):
        command.add_argument(
            "--yes", action="store_true", help="really delete"
        )
    args = parser.parse_args(argv)

    table = table or open_table(args.app_env)
    if args.command == "purge":
        now = now or datetime.now(timezone.utc)
        found = purge_older_than(table, args.older_than_days, now, args.yes)
    else:
        found = delete_by_email(table, args.email, args.yes)
    _report(found, args.yes)


if __name__ == "__main__":
    main()
