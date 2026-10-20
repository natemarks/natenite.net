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
def test_the_distribution_is_protected_by_the_shared_web_acl():
    """Without the ACL, neither the rate limit nor the managed rules apply."""
    polls_template().has_resource_properties(
        "AWS::CloudFront::Distribution",
        {"DistributionConfig": {"WebACLId": assertions.Match.any_value()}},
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
    """A fixed-name log group: 365 days of history, kept if the stack goes."""
    template = polls_template()
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {
            # The owner's log check reads this exact name.
            "LogGroupName": "/natenite/production/polls/submit",
            "RetentionInDays": 365,
        },
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
