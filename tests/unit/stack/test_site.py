#!/usr/bin/env python3
"""Golden tests for the Site stack template.

Purpose:
- Stack synthesis from real environment config under `config/<env>/...`.
- Verify Site stack dependency on Certificate stack.
- Include the Polls stack so the Site template matches the deployed one.

Customize:
- Keep the `*_actual` test for real environment contracts.
- Use `--update_golden` only when template changes are intentional.
"""

# pylint: disable=duplicate-code
import dataclasses

import pytest
from aws_cdk import App, assertions, Environment
from config.settings import PollsSetting, get_actual_path
from config.project import APP_ENV_TO_AWS_ACCOUNT
from stack.certificate import CertificateStack, CertificateInput
from stack.polls import PollsStack, PollsInput
from stack.site import SiteStack, SiteInput
from tests.helper import case_data_path, write_case_json, read_case_json


@pytest.mark.unit
@pytest.mark.parametrize(
    "environment",
    [
        pytest.param("production", id="production"),
    ],
)
def test_site_stack_actual(request, environment, update_golden):
    """Compare Site template against golden data for real environments."""
    # use stack input data from actual environments
    input_path = get_actual_path(environment)
    # test_data path for case
    data_path = case_data_path(request)

    # Create input objects
    cert_input = CertificateInput.from_config_directory(input_path)
    site_input = SiteInput.from_config_directory(input_path)

    app = App()

    # Use actual account for from_lookup to work
    cdk_env = Environment(
        account=APP_ENV_TO_AWS_ACCOUNT[environment],
        region="us-east-1",
    )

    # Create certificate stack first (dependency)
    cert_stack = CertificateStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=cert_input,
    )

    # Create site stack with certificate stack dependency
    site_stack = SiteStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=site_input,
        certificate_stack=cert_stack,
    )

    # The Polls stack attaches this stack's web ACL; building it makes the
    # Site template match the one deployed (it gains the ACL export).
    PollsStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=PollsInput.from_config_directory(input_path),
        certificate_stack=cert_stack,
        site_stack=site_stack,
    )

    template = assertions.Template.from_stack(site_stack)
    if update_golden:
        write_case_json(data_path, "expected.json", template.to_json())

    # Exact equality: template_matches ignores extra sections and properties,
    # so it would not notice an unintended change to the shared ACL.
    assert template.to_json() == read_case_json(data_path, "expected.json")


def site_template(polls_setting=None):
    """Synthesize the Site stack from real config, optionally overriding the
    polls settings its rate rule is built from."""
    input_path = get_actual_path("production")
    app = App()
    cdk_env = Environment(
        account=APP_ENV_TO_AWS_ACCOUNT["production"], region="us-east-1"
    )
    cert_stack = CertificateStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=CertificateInput.from_config_directory(input_path),
    )
    site_input = SiteInput.from_config_directory(input_path)
    if polls_setting is not None:
        site_input = dataclasses.replace(
            site_input, polls_setting=polls_setting
        )
    site_stack = SiteStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=site_input,
        certificate_stack=cert_stack,
    )
    return assertions.Template.from_stack(site_stack)


def rate_rule(host="polls.natenite.net", limit=20, window=300):
    """What the polls submit rate rule must look like in the template."""
    return {
        "Name": "PollsSubmitRateLimit",
        "Priority": 0,
        "Action": {"Block": {}},
        "Statement": {
            "RateBasedStatement": {
                "Limit": limit,
                "AggregateKeyType": "IP",
                "EvaluationWindowSec": window,
                "ScopeDownStatement": {
                    "AndStatement": {
                        "Statements": [
                            {  # the polls host (the Host header is lower-cased)
                                "ByteMatchStatement": {
                                    "FieldToMatch": {
                                        "SingleHeader": {"Name": "host"}
                                    },
                                    "PositionalConstraint": "EXACTLY",
                                    "SearchString": host,
                                    "TextTransformations": [
                                        {"Priority": 0, "Type": "LOWERCASE"}
                                    ],
                                }
                            },
                            {  # the submit path, exactly
                                "ByteMatchStatement": {
                                    "FieldToMatch": {"UriPath": {}},
                                    "PositionalConstraint": "EXACTLY",
                                    "SearchString": "/submit",
                                    "TextTransformations": [
                                        {"Priority": 0, "Type": "NONE"}
                                    ],
                                }
                            },
                            {  # POST only: page views are never counted
                                "ByteMatchStatement": {
                                    "FieldToMatch": {"Method": {}},
                                    "PositionalConstraint": "EXACTLY",
                                    "SearchString": "POST",
                                    "TextTransformations": [
                                        {"Priority": 0, "Type": "NONE"}
                                    ],
                                }
                            },
                        ]
                    }
                },
            }
        },
        "VisibilityConfig": {
            "CloudWatchMetricsEnabled": True,
            "SampledRequestsEnabled": True,
            "MetricName": "PollsSubmitRateLimit",
        },
    }


@pytest.mark.unit
def test_the_rate_rule_is_built_from_the_polls_settings():
    """A different host, limit and window flow through; nothing is fixed."""
    custom = PollsSetting(
        subdomain="vote", rate_limit=30, rate_window_seconds=120
    )

    site_template(custom).has_resource_properties(
        "AWS::WAFv2::WebACL",
        {
            "Rules": assertions.Match.array_with(
                [rate_rule(host="vote.natenite.net", limit=30, window=120)]
            )
        },
    )
