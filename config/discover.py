#!/usr/bin/env python3
"""Discovery workflow for external configuration data.

Purpose:
- Query external AWS data required by stacks in each environment.
- Return updated settings models from discovery operations.
- Persist updated settings under `config/<env>/...`.

Flow:
- Parse target environment from CLI args.
- Build an environment-specific discovery runner.
- Discover updated setting values and write them back to JSON config files.

Customize:
- Add new discovery methods for additional settings classes.
- Extend environment subclasses to choose which stack IDs to refresh.
- Update rollout ids in `config/template_defaults.json`.
- Replace file persistence with another backend if needed.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import ClassVar

from config.helper import (
    check_app_env,
    check_aws_account,
    get_logger,
    latest_ecs_ami_id,
)
from config.project import SIMPLE_ASG_IDS_BY_ENV, SUPPORTED_APP_ENVS
from config.settings import (
    EnvironmentSetting,
    SimpleAsgSetting,
    get_actual_path,
)

mlog = get_logger(str(__name__))


def get_environment_id() -> str:
    """Return environment id from CLI args (`dev|staging|production`)."""
    parser = argparse.ArgumentParser(description="Get the environment ID.")
    parser.add_argument(
        "environment",
        type=str,
        choices=list(SUPPORTED_APP_ENVS),
        help="Environment ID (must be one of: dev, staging, production)",
    )
    args = parser.parse_args()
    return args.environment


def write_setting_json(setting_path: Path, setting: SimpleAsgSetting) -> None:
    """Write dataclass-based setting object to JSON with indentation."""
    setting_path.write_text(
        json.dumps(asdict(setting), indent=2), encoding="utf-8"
    )


class DiscoveryRunner:
    """Base class for environment-specific discovery updates.

    Subclasses select discovery targets through class variables.
    """

    SIMPLE_ASG_IDS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, app_env: str):
        """Validate environment/account and load environment settings."""
        check_app_env(app_env)
        check_aws_account(app_env)
        self.data_path = get_actual_path(app_env)
        self.environment_setting = EnvironmentSetting.from_data_path(
            self.data_path
        )

    def discover_simple_asg_setting(self, stack_id: str) -> SimpleAsgSetting:
        """Return SimpleAsgSetting with discovered external values applied."""
        mlog.info(
            "updating simple_asg: %s - %s",
            self.environment_setting.app_env,
            stack_id,
        )
        setting = SimpleAsgSetting.from_data_path(self.data_path, stack_id)
        setting.ami_id = latest_ecs_ami_id(
            self.environment_setting.default_region
        )
        return setting

    def update_simple_asg(self, stack_id: str) -> None:
        """Discover and persist updates for one SimpleAsg stack id."""
        setting = self.discover_simple_asg_setting(stack_id)
        setting_path = setting.setting_path(self.data_path, stack_id)
        write_setting_json(setting_path, setting)

    def update_config(self) -> None:
        """Run discovery updates for configured stack ids in this env."""
        for stack_id in self.SIMPLE_ASG_IDS:
            self.update_simple_asg(stack_id)


class DevDiscoveryRunner(DiscoveryRunner):
    """Discovery behavior for the dev environment."""

    SIMPLE_ASG_IDS = SIMPLE_ASG_IDS_BY_ENV["dev"]


class StagingDiscoveryRunner(DiscoveryRunner):
    """Discovery behavior for the staging environment."""

    SIMPLE_ASG_IDS = SIMPLE_ASG_IDS_BY_ENV["staging"]


class ProductionDiscoveryRunner(DiscoveryRunner):
    """Discovery behavior for the production environment."""

    SIMPLE_ASG_IDS = SIMPLE_ASG_IDS_BY_ENV["production"]


DISCOVERY_MAP: dict[str, type[DiscoveryRunner]] = {
    "dev": DevDiscoveryRunner,
    "staging": StagingDiscoveryRunner,
    "production": ProductionDiscoveryRunner,
}


def get_discovery_runner(app_env: str) -> DiscoveryRunner:
    """Return discovery runner implementation for environment."""
    if app_env in DISCOVERY_MAP:
        return DISCOVERY_MAP[app_env](app_env=app_env)
    raise ValueError(f"invalid environment for discovery: {app_env}")


def main() -> None:
    """Run discovery for requested environment."""
    get_discovery_runner(get_environment_id()).update_config()


if __name__ == "__main__":
    main()
