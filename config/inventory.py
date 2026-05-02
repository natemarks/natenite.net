#!/usr/bin/env python3
"""Environment-specific stack inventory for the CDK app.

Purpose:
- Select stacks to deploy per environment.
- Apply shared environment tags.

Flow:
- `get_inventory(app_env)` returns an `Inventory` subclass.
- `Inventory.deploy_stacks` creates stacks for the environment.

Customize:
- Add or remove stack factories in `deploy_stacks`.
- Enable termination protection per environment.
- Extend shared tags in `set_environment_tags`.
"""

from typing import ClassVar

from aws_cdk import App, Environment, Tags

from config.settings import EnvironmentSetting, get_actual_path
from config.helper import check_aws_account, check_app_env
from stack.app_vpc import AppVpcInput, AppVpcStack


class Inventory:
    """Base inventory for deploying stacks in one application environment.

    Subclasses customize rollout through class variables.
    """

    TERMINATION_PROTECTION: ClassVar[bool] = False

    def __init__(self, app_env: str):
        """Validate environment/account and load environment settings."""
        check_app_env(app_env)
        check_aws_account(app_env)
        self.data_path = get_actual_path(app_env)
        self.app_env = app_env
        self.unique_stacks: dict[str, AppVpcStack] = {}
        self.environment_setting = EnvironmentSetting.from_data_path(
            self.data_path
        )

    def deploy_stacks(self, app: App, cdk_env: Environment):
        """Deploy stacks for this environment."""
        self.app_vpc_stack(
            app,
            cdk_env,
            termination_protection=self.TERMINATION_PROTECTION,
        )

    def set_environment_tags(self, app: App):
        """Apply shared environment tags to all stacks in the app."""
        Tags.of(app).add("env_id", self.app_env)
        Tags.of(app).add("app_env", self.app_env)
        Tags.of(app).add("Environment", self.app_env)

    def app_vpc_stack(
        self, app: App, cdk_env: Environment, termination_protection: bool
    ) -> AppVpcStack:
        """Create and register the single AppVpc stack for this env."""
        s_input = AppVpcInput.from_config_directory(self.data_path)
        self.unique_stacks["app_vpc"] = AppVpcStack(
            scope=app,
            cdk_env=cdk_env,
            s_input=s_input,
            termination_protection=termination_protection,
        )
        return self.unique_stacks["app_vpc"]


class DevInventory(Inventory):
    """Inventory settings for the dev environment."""


class StagingInventory(Inventory):
    """Inventory settings for the staging environment."""


class ProductionInventory(Inventory):
    """Inventory settings for the production environment."""


# Dictionary to map setting types to dataclass constructors
INVENTORY_MAP: dict[str, type[Inventory]] = {
    "dev": DevInventory,
    "staging": StagingInventory,
    "production": ProductionInventory,
}


def get_inventory(app_env: str) -> Inventory:
    """Return the inventory object for the requested application environment."""
    if app_env in INVENTORY_MAP:
        return INVENTORY_MAP[app_env](app_env=app_env)
    raise ValueError(f"invalid environment for locations: {app_env}")
