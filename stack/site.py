"""Site stack and input models.

Purpose:
- Create S3 bucket for static site content with versioning.
- Create CloudFront distribution with WAF protection.
- Use ACM certificate from Certificate stack for HTTPS.

Flow:
- `SiteInput.from_config_directory` converts config JSON to typed input.
- `SiteStack` depends on `CertificateStack` for certificate and domain.
- Synthesizes S3 bucket, CloudFront distribution, and WAF WebACL.

Customize:
- WAF rules in the WebACL
- CloudFront cache behaviors
- S3 lifecycle policies
"""

from dataclasses import dataclass
from pathlib import Path
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_cloudfront as cloudfront,
    aws_iam as iam,
    aws_route53 as r53,
    aws_route53_targets as targets,
    aws_s3 as s3,
    aws_wafv2 as wafv2,
)
from aws_cdk.aws_cloudfront_origins import S3BucketOrigin
from aws_cdk import Environment as cdk_environment
from constructs import Construct
from config.helper import APP_NAME
from config.settings import EnvironmentSetting
from stack.certificate import CertificateStack


@dataclass(frozen=True, kw_only=True)
class SiteInput:
    """Typed input payload for `SiteStack`."""

    env_setting: EnvironmentSetting

    def prefix(self) -> str:
        """Return the stack/resource prefix for this environment."""
        return f"{APP_NAME}{self.env_setting.prefix()}Site"

    @classmethod
    def from_config_directory(cls, data_path: Path) -> "SiteInput":
        """Build Site input from `config/<env>/...` files."""

        return cls(
            env_setting=EnvironmentSetting.from_data_path(data_path),
        )


class SiteStack(Stack):
    """CDK stack that provisions static site infrastructure.

    Resources:
    - private S3 bucket with versioning for static content
    - CloudFront distribution with S3 origin
    - WAF WebACL attached to CloudFront
    - Uses ACM certificate from CertificateStack for HTTPS

    Dependencies:
    - CertificateStack (for certificate and domain)
    """

    def __init__(
        self,
        scope: Construct,
        cdk_env: cdk_environment,
        s_input: SiteInput,
        certificate_stack: CertificateStack,
        **kwargs,
    ):
        self.s_input = s_input
        self._prefix = s_input.prefix()
        super().__init__(
            scope=scope, id=f"{self._prefix}Stack", env=cdk_env, **kwargs
        )

        # Create private S3 bucket for site content
        self.site_bucket = s3.Bucket(
            self,
            f"{self._prefix}Bucket",
            bucket_name=(
                f"{APP_NAME.lower()}-{self.s_input.env_setting.app_env}"
                f"-site-content"
            ),
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Create Origin Access Control for CloudFront to access S3
        oac_config = cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
            name=f"{self._prefix}OAC",
            origin_access_control_origin_type="s3",
            signing_behavior="always",
            signing_protocol="sigv4",
            description=(
                "Origin Access Control for "
                f"{self.s_input.env_setting.default_fqdn}"
            ),
        )
        cfn_origin_access_control = cloudfront.CfnOriginAccessControl(
            self,
            f"{self._prefix}OAC",
            origin_access_control_config=oac_config,
        )

        # Create WAF WebACL for CloudFront
        # Note: WAF for CloudFront must be in us-east-1
        self.web_acl = wafv2.CfnWebACL(
            self,
            f"{self._prefix}WebACL",
            scope="CLOUDFRONT",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=f"{self._prefix}WebACL",
                sampled_requests_enabled=True,
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(
                        none={}
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=(
                            wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                                vendor_name="AWS",
                                name="AWSManagedRulesCommonRuleSet",
                            )
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesCommonRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesKnownBadInputsRuleSet",
                    priority=2,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(
                        none={}
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=(
                            wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                                vendor_name="AWS",
                                name="AWSManagedRulesKnownBadInputsRuleSet",
                            )
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name=("AWSManagedRulesKnownBadInputsRuleSet"),
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
        )

        # Create CloudFront distribution
        viewer_protocol = cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
        self.distribution = cloudfront.Distribution(
            self,
            f"{self._prefix}Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=S3BucketOrigin(self.site_bucket),
                viewer_protocol_policy=viewer_protocol,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=(
                    cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN
                ),
            ),
            domain_names=[
                self.s_input.env_setting.default_fqdn,
                f"www.{self.s_input.env_setting.default_fqdn}",
            ],
            certificate=certificate_stack.certificate,
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.minutes(5),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.minutes(5),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            web_acl_id=self.web_acl.attr_arn,
        )

        # Update CloudFront distribution to use OAC
        cfn_distribution = self.distribution.node.default_child
        oac_path = "DistributionConfig.Origins.0.OriginAccessControlId"
        cfn_distribution.add_property_override(
            oac_path,
            cfn_origin_access_control.attr_id,
        )
        oai_path = (
            "DistributionConfig.Origins.0"
            ".S3OriginConfig.OriginAccessIdentity"
        )
        cfn_distribution.add_property_override(
            oai_path,
            "",
        )

        # Grant CloudFront OAC access to S3 bucket via bucket policy
        # OAC uses a service principal, not an identity ARN
        self.site_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetObject"],
                resources=[self.site_bucket.arn_for_objects("*")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": Stack.of(self).format_arn(
                            service="cloudfront",
                            resource="distribution",
                            region="",
                            resource_name=self.distribution.distribution_id,
                        )
                    }
                },
            )
        )

        # Create Route53 A records for apex and www pointing to CloudFront
        r53.ARecord(
            self,
            f"{self._prefix}ApexRecord",
            zone=certificate_stack.public_r53_zone,
            record_name=self.s_input.env_setting.default_fqdn,
            target=r53.RecordTarget.from_alias(
                targets.CloudFrontTarget(self.distribution)
            ),
        )

        r53.ARecord(
            self,
            f"{self._prefix}WwwRecord",
            zone=certificate_stack.public_r53_zone,
            record_name=f"www.{self.s_input.env_setting.default_fqdn}",
            target=r53.RecordTarget.from_alias(
                targets.CloudFrontTarget(self.distribution)
            ),
        )
