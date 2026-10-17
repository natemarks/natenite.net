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
import dataclasses

import pytest
from aws_cdk import App, assertions, Environment
from config.helper import PROJECT_ROOT
from config.settings import PollsSetting, get_actual_path
from config.project import APP_ENV_TO_AWS_ACCOUNT
from stack.certificate import CertificateStack, CertificateInput
from stack.polls import PollsStack, PollsInput
from stack.site import SiteStack, SiteInput
from tests.unit.stack.test_site import site_template
from tests.helper import (
    case_data_path,
    normalize_asset_hashes,
    read_case_json,
    write_case_json,
)

ENVIRONMENT = "production"


def build_polls_stack(
    environment: str = ENVIRONMENT, outdir=None, polls_setting=None
):
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
    polls_input = PollsInput.from_config_directory(input_path)
    if polls_setting is not None:
        polls_input = dataclasses.replace(
            polls_input, polls_setting=polls_setting
        )
    return PollsStack(
        scope=app,
        cdk_env=cdk_env,
        s_input=polls_input,
        certificate_stack=cert_stack,
        site_stack=site_stack,
    )


def polls_template(
    environment: str = ENVIRONMENT, polls_setting=None
) -> assertions.Template:
    """Synthesize the Polls stack for a real environment's config."""
    return assertions.Template.from_stack(
        build_polls_stack(environment, polls_setting=polls_setting)
    )


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
def test_function_bundle_holds_only_the_modules_and_every_definition(
    tmp_path,
):
    """The deployed bundle has the modules, real definition files, no caches."""
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
    modules = {"handler.py", "limits.py", "definitions.py"}
    assert files == modules | definitions
    assert not (asset_dir / "polls").is_symlink()


@pytest.mark.unit
def test_function_logs_to_a_group_kept_for_a_year_and_after_teardown():
    """An explicit log group: 365 days of history, kept if the stack goes."""
    template = polls_template()
    template.has_resource_properties(
        "AWS::Logs::LogGroup", {"RetentionInDays": 365}
    )
    template.has_resource(
        "AWS::Logs::LogGroup",
        {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"},
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "handler.handler",
            "LoggingConfig": {"LogGroup": assertions.Match.any_value()},
        },
    )


SAVED_QUERIES = {
    "polls/rejections-by-reason": ['filter outcome = "rejected"', "by reason"],
    "polls/errors": ['filter level = "ERROR"', "errorType", "responseId"],
    "polls/submissions-per-day": [
        'filter outcome = "accepted"',
        "by pollId",
        "datefloor(@timestamp, 1d)",
    ],
    "polls/recent-requests": [
        'filter event = "submission"',
        "sort @timestamp desc",
        "limit 100",
    ],
}


@pytest.mark.unit
def test_the_routine_check_queries_are_saved_against_the_function_log_group():
    """Four saved Logs Insights queries, each searching the function's logs."""
    template = polls_template().to_json()
    log_groups = [
        name
        for name, resource in template["Resources"].items()
        if resource["Type"] == "AWS::Logs::LogGroup"
    ]
    saved = {
        resource["Properties"]["Name"]: resource["Properties"]
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::Logs::QueryDefinition"
    }

    assert sorted(saved) == sorted(SAVED_QUERIES)
    for name, fragments in SAVED_QUERIES.items():
        assert saved[name]["LogGroupNames"] == [{"Ref": log_groups[0]}]
        for fragment in fragments:
            assert fragment in saved[name]["QueryString"], (name, fragment)


@pytest.mark.unit
def test_there_are_no_alarms_and_no_notification_topics():
    """The owner checks periodically by hand; nothing pages anyone."""
    types = {
        resource["Type"]
        for resource in polls_template().to_json()["Resources"].values()
    }

    assert "AWS::CloudWatch::Alarm" not in types
    assert "AWS::CloudWatch::CompositeAlarm" not in types
    assert "AWS::SNS::Topic" not in types


def submit_function_properties(template):
    """The properties of the submit function in a synthesized template."""
    return next(
        resource["Properties"]
        for resource in template.to_json()["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
        and resource["Properties"].get("Handler") == "handler.handler"
    )


@pytest.mark.unit
def test_production_reserves_no_concurrency_while_the_quota_is_too_low():
    """Unset in settings: no reservation, so the deploy works on a quota of 10."""
    properties = submit_function_properties(polls_template())

    assert "ReservedConcurrentExecutions" not in properties


@pytest.mark.unit
def test_a_reservation_in_settings_is_applied_to_the_function():
    """Once the quota is raised, setting a number is the only change needed."""
    setting = PollsSetting(
        subdomain="polls",
        rate_limit=20,
        rate_window_seconds=300,
        reserved_concurrency=2,
    )

    properties = submit_function_properties(
        polls_template(polls_setting=setting)
    )

    assert properties["ReservedConcurrentExecutions"] == 2


@pytest.mark.unit
def test_the_rate_rule_watches_the_host_and_path_the_polls_site_serves():
    """Rename the submit path or the host in one place and this fails."""
    site = site_template().to_json()["Resources"]
    acl = next(
        r["Properties"]
        for r in site.values()
        if r["Type"] == "AWS::WAFv2::WebACL"
    )
    rule = next(r for r in acl["Rules"] if r["Name"] == "PollsSubmitRateLimit")
    statements = rule["Statement"]["RateBasedStatement"]["ScopeDownStatement"][
        "AndStatement"
    ]["Statements"]
    watched_host, watched_path, watched_method = (
        s["ByteMatchStatement"]["SearchString"] for s in statements
    )

    polls = polls_template().to_json()["Resources"]
    distribution = next(
        r["Properties"]["DistributionConfig"]
        for r in polls.values()
        if r["Type"] == "AWS::CloudFront::Distribution"
    )
    (submit_behavior,) = distribution["CacheBehaviors"]

    assert watched_host in distribution["Aliases"]
    assert watched_path == submit_behavior["PathPattern"]
    assert watched_method in submit_behavior["AllowedMethods"]


def _access_log_bucket(template):
    """The one bucket that expires its objects: the access log bucket."""
    buckets = {
        name: body
        for name, body in template.find_resources("AWS::S3::Bucket").items()
        if "LifecycleConfiguration" in body["Properties"]
    }
    assert len(buckets) == 1
    return buckets.popitem()


@pytest.mark.unit
def test_access_logs_go_to_a_private_bucket_that_expires_them_after_a_year():
    """Access logs are kept privately for a year, and survive teardown."""
    template = polls_template()
    _, bucket = _access_log_bucket(template)
    props = bucket["Properties"]
    assert props["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }
    rules = props["LifecycleConfiguration"]["Rules"]
    assert [(rule["Status"], rule["ExpirationInDays"]) for rule in rules] == [
        ("Enabled", 365)
    ]
    assert bucket["DeletionPolicy"] == "Retain"


@pytest.mark.unit
def test_log_delivery_may_write_only_from_this_accounts_delivery_sources():
    """Only this account's log delivery may write into the log bucket."""
    template = polls_template()
    name, _ = _access_log_bucket(template)
    policies = [
        policy
        for policy in template.find_resources("AWS::S3::BucketPolicy").values()
        if policy["Properties"]["Bucket"] == {"Ref": name}
    ]
    assert len(policies) == 1
    statements = [
        statement
        for statement in policies[0]["Properties"]["PolicyDocument"][
            "Statement"
        ]
        if statement.get("Principal")
        == {"Service": "delivery.logs.amazonaws.com"}
    ]
    assert len(statements) == 1
    statement = statements[0]
    assert statement["Effect"] == "Allow"
    assert statement["Action"] == "s3:PutObject"
    condition = statement["Condition"]
    assert condition["StringEquals"]["s3:x-amz-acl"] == (
        "bucket-owner-full-control"
    )
    assert condition["StringEquals"]["aws:SourceAccount"] == (
        APP_ENV_TO_AWS_ACCOUNT[ENVIRONMENT]
    )
    assert "delivery-source:*" in str(condition["ArnLike"]["aws:SourceArn"])


@pytest.mark.unit
def test_the_distribution_delivers_json_access_logs_to_the_log_bucket():
    """The distribution's access logs reach the bucket as JSON."""
    template = polls_template()
    bucket_name, _ = _access_log_bucket(template)
    ((source_id, source),) = template.find_resources(
        "AWS::Logs::DeliverySource"
    ).items()
    ((destination_id, destination),) = template.find_resources(
        "AWS::Logs::DeliveryDestination"
    ).items()
    ((_, delivery),) = template.find_resources("AWS::Logs::Delivery").items()

    assert source["Properties"]["LogType"] == "ACCESS_LOGS"
    assert "Distribution" in str(source["Properties"]["ResourceArn"])
    assert destination["Properties"]["OutputFormat"] == "json"
    assert bucket_name in str(
        destination["Properties"]["DestinationResourceArn"]
    )
    assert "cloudfront/polls" in str(
        destination["Properties"]["DestinationResourceArn"]
    )
    props = delivery["Properties"]
    assert props["DeliverySourceName"] == {"Ref": source_id}
    assert props["DeliveryDestinationArn"] == {
        "Fn::GetAtt": [destination_id, "Arn"]
    }
    assert props["S3EnableHiveCompatiblePath"] is True


@pytest.mark.unit
def test_the_delivery_waits_for_the_bucket_policy_that_lets_it_write():
    """The delivery is created only after the policy allowing it."""
    template = polls_template()
    bucket_name, _ = _access_log_bucket(template)
    policy_ids = [
        name
        for name, policy in template.find_resources(
            "AWS::S3::BucketPolicy"
        ).items()
        if policy["Properties"]["Bucket"] == {"Ref": bucket_name}
    ]
    ((_, delivery),) = template.find_resources("AWS::Logs::Delivery").items()
    assert set(policy_ids) <= set(delivery.get("DependsOn", []))
