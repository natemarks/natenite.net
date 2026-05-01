#!/usr/bin/env python3
"""Environment-specific stack inventory for the CDK app.

Purpose:
- Select stacks to deploy per environment.
- Apply shared environment tags.
- Enforce stack dependency order (AppVpc before SimpleAsg).

Flow:
- `get_inventory(app_env)` returns an `Inventory` subclass.
- `Inventory.deploy_stacks` creates AppVpc, then one SimpleAsg per
  `SIMPLE_ASG_IDS` entry.

Customize:
- Add or remove stack factories in `deploy_stacks`.
- Change rollout ids in `config/template_defaults.json`.
- Enable termination protection per environment.
- Extend shared tags in `set_environment_tags`.
"""

from typing import ClassVar

from aws_cdk import App, Environment, Tags

from config.settings import EnvironmentSetting, get_actual_path
from config.project import SIMPLE_ASG_IDS_BY_ENV
from config.helper import check_aws_account, check_app_env
from stack.app_vpc import AppVpcInput, AppVpcStack
from stack.simple_asg import SimpleAsgInput, SimpleAsgStack


class Inventory:
    """Base inventory for deploying stacks in one application environment.

    Subclasses customize rollout through class variables.
    """

    SIMPLE_ASG_IDS: ClassVar[tuple[str, ...]] = ()
    TERMINATION_PROTECTION: ClassVar[bool] = False

    def __init__(self, app_env: str):
        """Validate environment/account and load environment settings."""
        check_app_env(app_env)
        check_aws_account(app_env)
        self.data_path = get_actual_path(app_env)
        self.app_env = app_env
        self.unique_stacks: dict[str, AppVpcStack] = {}
        self.multi_stacks: dict[str, dict[str, SimpleAsgStack]] = {}
        self.environment_setting = EnvironmentSetting.from_data_path(
            self.data_path
        )

    def deploy_stacks(self, app: App, cdk_env: Environment):
        """Deploy stacks in dependency order for this environment."""
        self.app_vpc_stack(
            app,
            cdk_env,
            termination_protection=self.TERMINATION_PROTECTION,
        )
        for stack_id in self.SIMPLE_ASG_IDS:
            self.simple_asg_stack(
                app,
                cdk_env,
                stack_id,
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

    def simple_asg_stack(
        self,
        app: App,
        cdk_env: Environment,
        stack_id: str,
        termination_protection: bool,
    ) -> SimpleAsgStack:
        """Create and register one SimpleAsg stack instance.

        The AppVpc stack must already exist because SimpleAsg consumes the VPC.
        """
        app_vpc_stack = self.unique_stacks.get("app_vpc")
        if app_vpc_stack is None:
            raise RuntimeError(
                "app_vpc stack must be created before simple_asg stacks"
            )

        simple_asg_stacks = self.multi_stacks.setdefault("simple_asg", {})

        s_input = SimpleAsgInput.from_config_directory(
            self.data_path, stack_id
        )
        simple_asg_stacks[stack_id] = SimpleAsgStack(
            scope=app,
            cdk_env=cdk_env,
            s_input=s_input,
            app_vpc_stack=app_vpc_stack,
            termination_protection=termination_protection,
        )
        return simple_asg_stacks[stack_id]


class DevInventory(Inventory):
    """Inventory settings for the dev environment.

    Commonly changed for new projects:
    - number of SimpleAsg instances (`SIMPLE_ASG_IDS`)
    - termination protection policy
    """

    SIMPLE_ASG_IDS = SIMPLE_ASG_IDS_BY_ENV["dev"]


class StagingInventory(Inventory):
    """Inventory settings for the staging environment."""

    SIMPLE_ASG_IDS = SIMPLE_ASG_IDS_BY_ENV["staging"]


class ProductionInventory(Inventory):
    """Inventory settings for the production environment."""

    SIMPLE_ASG_IDS = SIMPLE_ASG_IDS_BY_ENV["production"]


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
