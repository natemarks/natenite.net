"""Unit tests for `config.settings` behavior.

Purpose:
- Verify environment config path resolution.
- Verify settings model loading semantics used by stack constructors.
"""

import pytest

from config.settings import EnvironmentSetting, PollsSetting, get_actual_path
from tests.unit.config.settings._shared import APP_ENVS, expected_config_path


@pytest.mark.unit
@pytest.mark.parametrize(
    "environment",
    [pytest.param(value, id=value) for value in APP_ENVS],
)
def test_get_actual_environment(environment):
    """get_actual_path points at config/<environment>."""
    assert expected_config_path(environment) == get_actual_path(environment)


@pytest.mark.unit
def test_environment_factory_reads_expected_environment():
    """EnvironmentSetting.from_data_path returns the expected model."""
    data_path = get_actual_path("production")
    result = EnvironmentSetting.from_data_path(data_path)

    assert isinstance(result, EnvironmentSetting)
    assert result.app_env == "production"


@pytest.mark.unit
def test_polls_setting_reads_production_subdomain():
    """PollsSetting.from_data_path returns the polls subdomain."""
    data_path = get_actual_path("production")
    result = PollsSetting.from_data_path(data_path)

    assert isinstance(result, PollsSetting)
    assert result.subdomain == "polls"


@pytest.mark.unit
def test_polls_setting_reads_the_rate_limit_and_leaves_the_reservation_unset():
    """20 submits per 300 seconds per address; no concurrency reservation."""
    result = PollsSetting.from_data_path(get_actual_path("production"))

    assert result.rate_limit == 20
    assert result.rate_window_seconds == 300
    # The account's Lambda quota (10) is too low to reserve any; see slice 10.
    assert result.reserved_concurrency is None
