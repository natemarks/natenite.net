# Project Overview

AWS CDK infrastructure project using Python for multi-environment deployments.

## Configuration Architecture

- **`config/settings.py`**: Dataclasses for accessing per-environment JSON configuration files
  - Each settings class inherits from `JsonSettingBase` and defines a `RELATIVE_PATH_TEMPLATE`
  - JSON files located in `config/<environment>/...`
  - Examples: `EnvironmentSetting`, `SimpleAsgSetting`, `AppVpcSetting`

- **`config/project.py`**: Project-level helper functions and constants
  - Loads `config/template_defaults.json` for cross-cutting project metadata
  - Provides typed constants: `APP_NAME`, `SUPPORTED_APP_ENVS`, account mappings

- **`config/inventory.py`**: Determines which stacks are deployed in which environments
  - Environment-specific `Inventory` subclasses (Dev, Staging, Production)
  - Controls stack rollout order (AppVpc before SimpleAsg)
  - Manages termination protection settings per environment

- **`config/discover.py`**: Updates settings data based on external AWS lookups
  - Queries external data (e.g., latest ECS AMI IDs) and persists to JSON
  - Run via CLI: `python config/discover.py <environment>`

## Stack Module Pattern

Stack modules follow a consistent pattern with two classes:

1. **Input class**: Composed of settings objects, provides typed inputs to the stack
   - Example: `SimpleAsgInput` contains `EnvironmentSetting` + `SimpleAsgSetting`
   - Loaded via `from_config_directory(data_path, ...)`

2. **Stack class**: CDK Stack implementation that consumes the input class
   - Example: `SimpleAsgStack` receives `SimpleAsgInput` and `AppVpcStack` dependency

## Testing & Quality

- **`make static`**: Run formatters, linters, and unit tests (use this during development)
- **`make static-check`**: Read-only check gate for CI/branch protection
- **`make unit-test`**: Run unit tests only
- **`make unit-update_golden`**: Update golden files for parameter tests

## Testing Requirements

Every stack must have a parameter test for each environment that tests for template changes. These tests ensure CloudFormation template stability across deployments.
