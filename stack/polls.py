"""Polls stack and input models.

Purpose:
- Serve the shared poll page and poll definitions at the polls hostname.
- Reuse the ACM certificate from the Certificate stack and the web ACL from
  the Site stack.

Flow:
- `PollsInput.from_config_directory` converts config JSON to typed input.
- `PollsStack` depends on `CertificateStack` and `SiteStack`.
- Synthesizes an S3 bucket and a CloudFront distribution.

Customize:
- the polls subdomain in `config/<env>/polls/polls.json`
- CloudFront cache behaviors
"""

# pylint: disable=duplicate-code
from dataclasses import dataclass
from pathlib import Path
from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    SymlinkFollowMode,
    aws_cloudfront as cloudfront,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_route53 as r53,
    aws_route53_targets as targets,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
)
from aws_cdk.aws_cloudfront_origins import FunctionUrlOrigin, S3BucketOrigin
from aws_cdk import Environment as cdk_environment
from constructs import Construct
from config.helper import APP_NAME, PROJECT_ROOT
from config.settings import EnvironmentSetting, PollsSetting
from stack.certificate import CertificateStack
from stack.site import SiteStack


@dataclass(frozen=True, kw_only=True)
class PollsInput:
    """Typed input payload for `PollsStack`."""

    env_setting: EnvironmentSetting
    polls_setting: PollsSetting

    def prefix(self) -> str:
        """Return the stack/resource prefix for this environment."""
        return f"{APP_NAME}{self.env_setting.prefix()}Polls"

    def fqdn(self) -> str:
        """Return the fully qualified host name that serves the polls."""
        return self.polls_setting.fqdn(self.env_setting.default_fqdn)

    def stack_name(self) -> str:
        """Return the CloudFormation stack name (the log check looks it up)."""
        return f"{self.prefix()}Stack"

    def table_name(self) -> str:
        """Return the responses table name (shared with the owner scripts)."""
        return f"{APP_NAME.lower()}-{self.env_setting.app_env}-polls-responses"

    def log_group_name(self) -> str:
        """Return the submit function's log group name (the log check reads it)."""
        return f"/{APP_NAME.lower()}/{self.env_setting.app_env}/polls/submit"

    @classmethod
    def from_config_directory(cls, data_path: Path) -> "PollsInput":
        """Build Polls input from `config/<env>/...` files."""

        return cls(
            env_setting=EnvironmentSetting.from_data_path(data_path),
            polls_setting=PollsSetting.from_data_path(data_path),
        )


class PollsStack(Stack):
    """CDK stack that serves polls on their own CloudFront distribution.

    Resources:
    - private S3 bucket holding the poll page and poll definitions
    - CloudFront distribution at the polls hostname using the shared
      certificate and the shared web ACL

    Dependencies:
    - CertificateStack (for certificate)
    - SiteStack (for web ACL)
    """

    def __init__(
        self,
        scope: Construct,
        cdk_env: cdk_environment,
        s_input: PollsInput,
        certificate_stack: CertificateStack,
        site_stack: SiteStack,
        **kwargs,
    ):
        self.s_input = s_input
        self._prefix = s_input.prefix()
        super().__init__(
            scope=scope, id=s_input.stack_name(), env=cdk_env, **kwargs
        )

        # Page and definitions are rebuilt from the repository on deploy
        self.site_bucket = s3.Bucket(
            self,
            f"{self._prefix}Bucket",
            bucket_name=(
                f"{APP_NAME.lower()}-{self.s_input.env_setting.app_env}"
                f"-polls-site-content"
            ),
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Gathered responses cannot be rebuilt: keep the table when the stack
        # goes away and require a deliberate step to delete it. Point-in-time
        # recovery stays off because it would keep deleted emails for 35 days.
        self.responses_table = dynamodb.Table(
            self,
            f"{self._prefix}ResponsesTable",
            table_name=self.s_input.table_name(),
            partition_key=dynamodb.Attribute(
                name="pk", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sk", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # The function's log group: a year of history, kept if the stack is
        # deleted (the lines hold no personal data). Without this, Lambda
        # makes a group that never expires and is not managed here. The name
        # is fixed so the owner's log check can find the group.
        log_group = logs.LogGroup(
            self,
            f"{self._prefix}SubmitLogGroup",
            log_group_name=self.s_input.log_group_name(),
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # The submit function. `polls` inside its folder is a symlink to the
        # repository's poll definitions; following it bundles the real files.
        self.submit_function = lambda_.Function(
            self,
            f"{self._prefix}SubmitFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(
                str(PROJECT_ROOT / "lambda" / "submit"),
                follow_symlinks=SymlinkFollowMode.ALWAYS,
                exclude=["__pycache__", "*.pyc"],
            ),
            memory_size=256,
            timeout=Duration.seconds(10),
            environment={"TABLE_NAME": self.responses_table.table_name},
            log_group=log_group,
            # Optional: Lambda cannot reserve any concurrency while the
            # account quota is as low as 10 (see PollsSetting).
            reserved_concurrent_executions=(
                self.s_input.polls_setting.reserved_concurrency
            ),
        )
        self.responses_table.grant(self.submit_function, "dynamodb:PutItem")
        # IAM auth: only CloudFront (through OAC) may call the function URL
        self.submit_url = self.submit_function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.AWS_IAM
        )

        # Poll addresses have no file extension (/poll1, /poll1/): serve the
        # shared page for them. Files such as /app.js or
        # /definitions/poll1.json pass through unchanged.
        poll_page_rewrite = cloudfront.Function(
            self,
            f"{self._prefix}PollPageRewriteFunction",
            code=cloudfront.FunctionCode.from_inline("""
function handler(event) {
    var request = event.request;
    var lastSegment = request.uri.split('/').pop();
    if (lastSegment.indexOf('.') === -1) {
        request.uri = '/index.html';
    }
    return request;
}
            """),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
            comment="Serve the shared poll page for poll addresses",
        )

        self.distribution = cloudfront.Distribution(
            self,
            f"{self._prefix}Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=S3BucketOrigin.with_origin_access_control(
                    self.site_bucket
                ),
                viewer_protocol_policy=(
                    cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
                ),
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=poll_page_rewrite,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            additional_behaviors={
                "/submit": cloudfront.BehaviorOptions(
                    origin=FunctionUrlOrigin.with_origin_access_control(
                        self.submit_url
                    ),
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=(
                        cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
                    ),
                    viewer_protocol_policy=(
                        cloudfront.ViewerProtocolPolicy.HTTPS_ONLY
                    ),
                )
            },
            domain_names=[self.s_input.fqdn()],
            certificate=certificate_stack.certificate,
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            web_acl_id=site_stack.web_acl.attr_arn,
        )

        # Alias record for the polls hostname in the existing hosted zone
        r53.ARecord(
            self,
            f"{self._prefix}AliasRecord",
            zone=certificate_stack.public_r53_zone,
            record_name=self.s_input.fqdn(),
            target=r53.RecordTarget.from_alias(
                targets.CloudFrontTarget(self.distribution)
            ),
        )

        # The shared page goes at the bucket root. Excluding the definitions
        # prefix keeps this deployment from pruning the definitions.
        s3deploy.BucketDeployment(
            self,
            f"{self._prefix}PageDeployment",
            sources=[
                s3deploy.Source.asset(str(PROJECT_ROOT / "site" / "polls"))
            ],
            destination_bucket=self.site_bucket,
            exclude=["definitions/*"],
            prune=True,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        # Poll definitions live under their own prefix; pruning only touches
        # that prefix, so removing a poll file unpublishes the poll.
        s3deploy.BucketDeployment(
            self,
            f"{self._prefix}DefinitionsDeployment",
            sources=[s3deploy.Source.asset(str(PROJECT_ROOT / "polls"))],
            destination_bucket=self.site_bucket,
            destination_key_prefix="definitions",
            prune=True,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )
