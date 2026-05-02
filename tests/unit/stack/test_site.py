#!/usr/bin/env python3
"""Golden tests for the Site stack template.

Purpose:
- Stack synthesis from real environment config under `config/<env>/...`.
- Verify Site stack dependency on Certificate stack.

Customize:
- Keep the `*_actual` test for real environment contracts.
- Use `--update_golden` only when template changes are intentional.
"""

# pylint: disable=duplicate-code
import pytest
from aws_cdk import App, assertions, Environment
from config.settings import get_actual_path
from stack.certificate import CertificateStack, CertificateInput
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

    # Create certificate stack first (dependency)
    cert_stack = CertificateStack(
        scope=app,
        cdk_env=Environment(),
        s_input=cert_input,
    )

    # Create site stack with certificate stack dependency
    site_stack = SiteStack(
        scope=app,
        cdk_env=Environment(),
        s_input=site_input,
        certificate_stack=cert_stack,
    )

    template = assertions.Template.from_stack(site_stack)
    if update_golden:
        write_case_json(data_path, "expected.json", template.to_json())

    template.template_matches(read_case_json(data_path, "expected.json"))
