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
- Replace file persistence with another backend if needed.
"""

import argparse

from config.helper import (
    check_app_env,
    check_aws_account,
    get_logger,
)
from config.project import SUPPORTED_APP_ENVS
from config.settings import (
    EnvironmentSetting,
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


class DiscoveryRunner:
    """Base class for environment-specific discovery updates.

    Subclasses select discovery targets through class variables.
    """

    def __init__(self, app_env: str):
        """Validate environment/account and load environment settings."""
        check_app_env(app_env)
        check_aws_account(app_env)
        self.data_path = get_actual_path(app_env)
        self.environment_setting = EnvironmentSetting.from_data_path(
            self.data_path
        )

    def update_config(self) -> None:
        """Run discovery updates for configured stack ids in this env."""


class DevDiscoveryRunner(DiscoveryRunner):
    """Discovery behavior for the dev environment."""


class StagingDiscoveryRunner(DiscoveryRunner):
    """Discovery behavior for the staging environment."""


class ProductionDiscoveryRunner(DiscoveryRunner):
    """Discovery behavior for the production environment."""


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
