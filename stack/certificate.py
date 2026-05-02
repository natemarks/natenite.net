"""Certificate stack and input models.

Purpose:
- Create a public hosted zone for the environment domain.
- Create an ACM certificate with DNS validation for the domain and wildcard.

Flow:
- `CertificateInput.from_config_directory` converts config JSON to typed input.
- `CertificateStack` synthesizes the hosted zone and certificate.

Customize:
- domain name comes from `EnvironmentSetting.default_fqdn`
"""

from dataclasses import dataclass
from pathlib import Path
from aws_cdk import (
    Stack,
    aws_certificatemanager as acm,
    aws_route53 as r53,
)
from aws_cdk import Environment as cdk_environment
from constructs import Construct
from config.helper import APP_NAME
from config.settings import EnvironmentSetting


@dataclass(frozen=True, kw_only=True)
class CertificateInput:
    """Typed input payload for `CertificateStack`."""

    env_setting: EnvironmentSetting

    def prefix(self) -> str:
        """Return the stack/resource prefix for this environment."""
        return f"{APP_NAME}{self.env_setting.prefix()}Certificate"

    @classmethod
    def from_config_directory(cls, data_path: Path) -> "CertificateInput":
        """Build Certificate input from `config/<env>/...` files."""

        return cls(
            env_setting=EnvironmentSetting.from_data_path(data_path),
        )


class CertificateStack(Stack):
    """CDK stack that provisions a public hosted zone and ACM certificate.

    Resources:
    - public Route53 hosted zone for the environment domain
    - ACM certificate for the environment domain and wildcard subdomain
    """

    def __init__(
        self,
        scope: Construct,
        cdk_env: cdk_environment,
        s_input: CertificateInput,
        **kwargs,
    ):
        self.s_input = s_input
        self._prefix = s_input.prefix()
        super().__init__(
            scope=scope, id=f"{self._prefix}Stack", env=cdk_env, **kwargs
        )
        self.public_r53_zone = r53.PublicHostedZone(
            self,
            f"{self._prefix}PublicR53Zone",
            zone_name=self.s_input.env_setting.default_fqdn,
        )
        self.certificate = acm.Certificate(
            self,
            f"{self._prefix}Certificate",
            domain_name=self.s_input.env_setting.default_fqdn,
            subject_alternative_names=[
                f"*.{self.s_input.env_setting.default_fqdn}"
            ],
            validation=acm.CertificateValidation.from_dns(
                self.public_r53_zone
            ),
        )
