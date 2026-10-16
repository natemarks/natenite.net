#!/usr/bin/env python3
"""Tests for the Polls stack template.

Purpose:
- Stack synthesis from real environment config under `config/<env>/...`.
- Verify Polls stack dependencies on the Certificate and Site stacks.
- Assert the behaviors that matter beyond the golden file.

Customize:
- Keep the `*_actual` golden test for real environment contracts.
- Use `--update_golden` only when template changes are intentional.
"""

# pylint: disable=duplicate-code
import pytest
from aws_cdk import App, assertions, Environment
from config.settings import get_actual_path
from config.project import APP_ENV_TO_AWS_ACCOUNT
from stack.certificate import CertificateStack, CertificateInput
from stack.polls import PollsStack, PollsInput
from stack.site import SiteStack, SiteInput
from tests.helper import (
    case_data_path,
    normalize_asset_hashes,
    read_case_json,
    write_case_json,
)

ENVIRONMENT = "production"


def polls_template(environment: str = ENVIRONMENT) -> assertions.Template:
    """Synthesize the Polls stack for a real environment's config."""
    input_path = get_actual_path(environment)
    app = App()
    cdk_env = Environment(
        account=APP_ENV_TO_AWS_ACCOUNT[environment],
        region="us-east-1",
    )
    cert_stack = CertificateStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=CertificateInput.from_config_directory(input_path),
    )
    site_stack = SiteStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=SiteInput.from_config_directory(input_path),
        certificate_stack=cert_stack,
    )
    polls_stack = PollsStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=PollsInput.from_config_directory(input_path),
        certificate_stack=cert_stack,
        site_stack=site_stack,
    )
    return assertions.Template.from_stack(polls_stack)


@pytest.mark.unit
def test_distribution_serves_polls_hostname_with_shared_certificate_and_acl():
    """The polls distribution uses the polls host, shared cert and ACL."""
    polls_template().has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": {
                "Aliases": ["polls.natenite.net"],
                "DefaultCacheBehavior": {
                    "ViewerProtocolPolicy": "redirect-to-https"
                },
                "ViewerCertificate": {
                    "AcmCertificateArn": assertions.Match.any_value()
                },
                "WebACLId": assertions.Match.any_value(),
            }
        },
    )


@pytest.mark.unit
def test_default_behavior_rewrites_poll_paths_at_viewer_request():
    """A viewer-request function maps poll paths to the shared page."""
    template = polls_template()
    template.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": {
                "DefaultCacheBehavior": {
                    "FunctionAssociations": [
                        {
                            "EventType": "viewer-request",
                            "FunctionARN": assertions.Match.any_value(),
                        }
                    ]
                }
            }
        },
    )
    template.has_resource_properties(
        "AWS::CloudFront::Function",
        {
            "FunctionCode": assertions.Match.string_like_regexp(
                ".*/index.html.*"
            )
        },
    )


@pytest.mark.unit
def test_polls_hostname_is_an_alias_to_the_distribution():
    """An A alias record in the existing zone points at the distribution."""
    polls_template().has_resource_properties(
        "AWS::Route53::RecordSet",
        {
            "Name": "polls.natenite.net.",
            "Type": "A",
            "AliasTarget": {
                "DNSName": {
                    "Fn::GetAtt": [
                        assertions.Match.string_like_regexp(
                            ".*Distribution.*"
                        ),
                        "DomainName",
                    ]
                }
            },
        },
    )


@pytest.mark.unit
def test_page_and_definitions_are_deployed_without_pruning_each_other():
    """Page at the root, definitions under a prefix; each prunes only itself."""
    template = polls_template()
    template.has_resource_properties(
        "Custom::CDKBucketDeployment",
        {
            "DestinationBucketKeyPrefix": "definitions",
            "Prune": True,
            "DistributionPaths": ["/*"],
        },
    )
    template.has_resource_properties(
        "Custom::CDKBucketDeployment",
        {
            "Exclude": ["definitions/*"],
            "Prune": True,
            "DistributionPaths": ["/*"],
        },
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "environment",
    [
        pytest.param("production", id="production"),
    ],
)
def test_polls_stack_actual(request, environment, update_golden):
    """Compare Polls template against golden data for real environments."""
    data_path = case_data_path(request)
    actual = normalize_asset_hashes(polls_template(environment).to_json())
    if update_golden:
        write_case_json(data_path, "expected.json", actual)

    assert actual == read_case_json(data_path, "expected.json")
