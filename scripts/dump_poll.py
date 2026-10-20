#!/usr/bin/env python3
"""Write one poll's stored responses to a git-ignored JSON file.

Purpose:
- Let the poll owner read results: one query per poll, in submission order.

Usage:
- PYTHONPATH=. python3 scripts/dump_poll.py <poll-id> [--emails]
  [--app-env production]
- `make dump-poll poll=<poll-id> [emails=1]`

Notes:
- The results go to `.polls-results/<poll-id>.json` (owner-only permissions,
  ignored by git); only a one-line summary is printed.
- Every response says whether its visitor left an email (`hasEmail`), so the
  share who did can be counted. The address itself (`email`) is included only
  with `--emails`: with it the file ties each answer to a person, so keep it
  out of the repository and out of shared places.
- An email record whose response was deleted separately cannot be joined; the
  script counts those on stderr (never printing an address).
"""

import argparse
import json
import os
import re
import sys
from decimal import Decimal

import boto3

from config.helper import PROJECT_ROOT
from config.settings import get_actual_path
from stack.polls import PollsInput

RESULTS_DIR = PROJECT_ROOT / ".polls-results"
RESPONSE_PREFIX = "RESPONSE#"
EMAIL_PREFIX = "EMAIL#"
# The same rule the poll files are held to: it also keeps the ID a plain file
# name, so it can never point outside the results folder.
_POLL_ID = re.compile(r"[a-z0-9-]+")


def _plain_number(value):
    """JSON encoder hook: DynamoDB returns numbers as Decimal."""
    if isinstance(value, Decimal):
        return (
            int(value) if value == value.to_integral_value() else float(value)
        )
    raise TypeError(f"cannot serialize {type(value).__name__}")


def fetch_records(table, poll_id):
    """Return every record of the poll (responses and emails), page by page."""
    items = []
    query = {
        "KeyConditionExpression": "pk = :pk",
        "ExpressionAttributeValues": {":pk": f"POLL#{poll_id}"},
    }
    while True:
        page = table.query(**query)
        items.extend(page["Items"])
        if "LastEvaluatedKey" not in page:
            return items
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def join_emails(records, include_addresses):
    """Return (responses, unmatched): each response says if it has an email.

    A response and its email record share an ID after their prefixes. With
    `include_addresses` each response also carries the address (or None).
    `unmatched` counts email records that have no response.
    """
    emails = {
        item["sk"].removeprefix(EMAIL_PREFIX): item["email"]
        for item in records
        if item["sk"].startswith(EMAIL_PREFIX)
    }
    responses = []
    for item in records:
        if not item["sk"].startswith(RESPONSE_PREFIX):
            continue
        address = emails.pop(item["sk"].removeprefix(RESPONSE_PREFIX), None)
        response = {**item, "hasEmail": address is not None}
        if include_addresses:
            response["email"] = address
        responses.append(response)
    return responses, len(emails)


def dump_poll(table, poll_id, include_emails=False, warnings=sys.stderr):
    """Return the poll's responses as indented JSON text."""
    responses, unmatched = join_emails(
        fetch_records(table, poll_id), include_emails
    )
    if unmatched:
        print(
            f"note: {unmatched} email record(s) have no matching response and"
            " are not shown (see make purge-emails and make delete-email)",
            file=warnings,
        )
    # Sorted keys: DynamoDB returns attributes in no fixed order, and the
    # output should be the same text for the same data (diffs, automation).
    return json.dumps(
        responses,
        indent=2,
        default=_plain_number,
        sort_keys=True,
    )


def results_path(poll_id, results_dir=RESULTS_DIR):
    """Return the file a poll's results are written to."""
    if not _POLL_ID.fullmatch(poll_id):
        raise ValueError(
            "a poll ID is lower-case letters, digits and hyphens only"
        )
    return results_dir / f"{poll_id}.json"


def write_results(path, text):
    """Write the results readable by the owner only, replacing any old file."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as results:
        results.write(text + "\n")


def open_table(app_env, resource=boto3.resource):
    """Open the environment's responses table in its configured region.

    The region comes from the environment's config, not from the caller's
    AWS settings: boto3 ignores AWS_REGION and a profile may set no region.
    """
    polls_input = PollsInput.from_config_directory(get_actual_path(app_env))
    region = polls_input.env_setting.default_region
    return resource("dynamodb", region_name=region).Table(
        polls_input.table_name()
    )


def main(argv=None, table=None, results_dir=RESULTS_DIR):
    """Write the poll named on the command line to its results file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("poll_id")
    parser.add_argument(
        "--emails",
        action="store_true",
        help="also include each visitor's email address",
    )
    parser.add_argument("--app-env", default="production")
    args = parser.parse_args(argv)

    try:
        path = results_path(args.poll_id, results_dir)
    except ValueError as error:
        parser.error(str(error))
    text = dump_poll(
        table or open_table(args.app_env), args.poll_id, args.emails
    )
    write_results(path, text)
    print(
        f"Wrote {len(json.loads(text))} response(s) to {path}"
        f" (email addresses {'included' if args.emails else 'not included'})"
    )


if __name__ == "__main__":
    main()
