#!/usr/bin/env python3
"""Dump one poll's stored responses as JSON.

Purpose:
- Let the poll owner read results: one query per poll, in submission order.

Usage:
- PYTHONPATH=. python3 scripts/dump_poll.py <poll-id> [--app-env production]
- `make dump-poll poll=<poll-id>`

Notes:
- Email addresses are stored as separate records and are not included.
"""

import argparse
import json
from decimal import Decimal

import boto3

from config.settings import get_actual_path
from stack.polls import PollsInput


def _plain_number(value):
    """JSON encoder hook: DynamoDB returns numbers as Decimal."""
    if isinstance(value, Decimal):
        return (
            int(value) if value == value.to_integral_value() else float(value)
        )
    raise TypeError(f"cannot serialize {type(value).__name__}")


def fetch_responses(table, poll_id):
    """Return every response record for the poll, following result pages."""
    items = []
    query = {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
        "ExpressionAttributeValues": {
            ":pk": f"POLL#{poll_id}",
            ":prefix": "RESPONSE#",
        },
    }
    while True:
        page = table.query(**query)
        items.extend(page["Items"])
        if "LastEvaluatedKey" not in page:
            return items
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def dump_poll(table, poll_id):
    """Return the poll's responses as indented JSON text."""
    return json.dumps(
        fetch_responses(table, poll_id), indent=2, default=_plain_number
    )


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


def main():
    """Print the responses of the poll named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("poll_id")
    parser.add_argument("--app-env", default="production")
    args = parser.parse_args()

    print(dump_poll(open_table(args.app_env), args.poll_id))


if __name__ == "__main__":
    main()
