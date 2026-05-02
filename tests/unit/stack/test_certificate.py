#!/usr/bin/env python3
"""Golden tests for the Certificate stack template.

Purpose:
- Stack synthesis from real environment config under `config/<env>/...`.

Customize:
- Keep the `*_actual` test for real environment contracts.
- Use `--update_golden` only when template changes are intentional.
"""

# pylint: disable=duplicate-code
import pytest
from aws_cdk import App, assertions, Environment
from config.settings import get_actual_path
from stack.certificate import CertificateStack, CertificateInput
from tests.helper import case_data_path, write_case_json, read_case_json


@pytest.mark.unit
@pytest.mark.parametrize(
    "environment",
    [
        pytest.param("production", id="production"),
    ],
)
def test_certificate_stack_actual(request, environment, update_golden):
    """Compare Certificate template against golden data for real environments."""
    # use stack input data from actual environments
    input_path = get_actual_path(environment)
    # test_data path for case
    data_path = case_data_path(request)
    s_input = CertificateInput.from_config_directory(input_path)

    app = App()

    stk = CertificateStack(
        scope=app,
        cdk_env=Environment(),
        s_input=s_input,
    )
    template = assertions.Template.from_stack(stk)
    if update_golden:
        write_case_json(data_path, "expected.json", template.to_json())

    template.template_matches(read_case_json(data_path, "expected.json"))
