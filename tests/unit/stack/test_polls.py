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
from config.helper import PROJECT_ROOT
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


def build_polls_stack(environment: str = ENVIRONMENT, outdir=None):
    """Build the Polls stack (and its dependencies) from real config."""
    input_path = get_actual_path(environment)
    app = App(outdir=str(outdir)) if outdir else App()
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
    return PollsStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=PollsInput.from_config_directory(input_path),
        certificate_stack=cert_stack,
        site_stack=site_stack,
    )


def polls_template(environment: str = ENVIRONMENT) -> assertions.Template:
    """Synthesize the Polls stack for a real environment's config."""
    return assertions.Template.from_stack(build_polls_stack(environment))


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


@pytest.mark.unit
def test_responses_table_is_on_demand_retained_and_protected():
    """Gathered responses survive stack deletion and table deletes."""
    template = polls_template()
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "natenite-production-polls-responses",
            "BillingMode": "PAY_PER_REQUEST",
            "DeletionProtectionEnabled": True,
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            # Backups would keep deleted email addresses for up to 35 days.
            "PointInTimeRecoverySpecification": assertions.Match.absent(),
        },
    )
    template.has_resource(
        "AWS::DynamoDB::Table",
        {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"},
    )


@pytest.mark.unit
def test_submit_function_may_only_put_items_in_the_responses_table():
    """The function gets the table name and write-only access to it."""
    template = polls_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.handler",
            "Environment": {
                "Variables": {
                    "TABLE_NAME": {
                        "Ref": assertions.Match.string_like_regexp(
                            ".*ResponsesTable.*"
                        )
                    }
                }
            },
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        {
                            "Action": "dynamodb:PutItem",
                            "Effect": "Allow",
                            "Resource": assertions.Match.any_value(),
                        }
                    ]
                )
            }
        },
    )


@pytest.mark.unit
def test_function_url_requires_iam_authentication():
    """The raw function address cannot be called without signing."""
    polls_template().has_resource_properties(
        "AWS::Lambda::Url", {"AuthType": "AWS_IAM"}
    )


@pytest.mark.unit
def test_submit_path_is_served_by_the_function_without_caching():
    """/submit takes every method over HTTPS and is never cached."""
    polls_template().has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": {
                "CacheBehaviors": [
                    {
                        "PathPattern": "/submit",
                        "AllowedMethods": [
                            "GET",
                            "HEAD",
                            "OPTIONS",
                            "PUT",
                            "PATCH",
                            "POST",
                            "DELETE",
                        ],
                        "ViewerProtocolPolicy": "https-only",
                        # AWS managed policies: CachingDisabled and
                        # AllViewerExceptHostHeader (the function URL needs
                        # its own Host header, not the viewer's).
                        "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                        "OriginRequestPolicyId": (
                            "b689b0a8-53d0-40ab-baf2-68738e2966ac"
                        ),
                        "TargetOriginId": assertions.Match.any_value(),
                    }
                ]
            }
        },
    )


@pytest.mark.unit
def test_function_origin_uses_lambda_origin_access_control():
    """CloudFront signs requests to the function URL with OAC."""
    polls_template().has_resource_properties(
        "AWS::CloudFront::OriginAccessControl",
        {
            "OriginAccessControlConfig": {
                "OriginAccessControlOriginType": "lambda",
                "SigningBehavior": "always",
                "SigningProtocol": "sigv4",
            }
        },
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "action", ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"]
)
def test_cloudfront_may_invoke_the_function(action):
    """Both permissions AWS now requires are granted to CloudFront."""
    polls_template().has_resource_properties(
        "AWS::Lambda::Permission",
        {
            "Action": action,
            "Principal": "cloudfront.amazonaws.com",
            "SourceArn": assertions.Match.any_value(),
        },
    )


@pytest.mark.unit
def test_function_bundle_holds_only_the_handler_limits_and_every_definition(
    tmp_path,
):
    """The deployed bundle has real definition files and no stray caches."""
    stack = build_polls_stack(outdir=tmp_path)
    template = assertions.Template.from_stack(stack).to_json()
    function = next(
        resource["Properties"]
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
        and resource["Properties"].get("Handler") == "handler.handler"
    )
    asset_dir = tmp_path / f"asset.{function['Code']['S3Key'][:-4]}"

    files = {
        str(path.relative_to(asset_dir))
        for path in asset_dir.rglob("*")
        if path.is_file()
    }

    # Expected from the source folder, so adding a poll needs no test edit
    definitions = {
        f"polls/{path.name}"
        for path in (PROJECT_ROOT / "polls").glob("*.json")
    }
    assert files == {"handler.py", "limits.py"} | definitions
    assert not (asset_dir / "polls").is_symlink()
