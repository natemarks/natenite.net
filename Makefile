.DEFAULT_GOAL := help

# Determine this makefile's path.
# Be sure to place this BEFORE `include` directives, if any.
SHELL := $(shell which bash)
DEFAULT_BRANCH := main
VERSION := 0.0.0
COMMIT := $(shell git rev-parse HEAD)
CDK := node_modules/.bin/cdk

CURRENT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD)
DEFAULT_BRANCH := main
app_env := production
PYTHON_VERSION := 3.12.13
CDK_VERSION := 2.70.0

help: ## Show this help.
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

clean-venv: ## re-create virtual env
	[[ -e .venv ]] && rm -rf .venv; \
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python3 -m venv .venv; \
       source .venv/bin/activate; \
       pip install --upgrade pip setuptools; \
       pip install -r requirements.txt; \
    )

.venv: ## create venv if it doesnt exist
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python3 -m venv .venv; \
       source .venv/bin/activate; \
       pip install --upgrade pip setuptools; \
       pip install -r requirements.txt; \
    )

update_cdk_libs: .venv ## install the latest version of aws cdk node and python packages
	bash scripts/update_cdk_libs.sh
	$(MAKE) clean-venv

pylint: .venv ## run pylint on python files
	( \
       . .venv/bin/activate; \
       git ls-files '*.py' | xargs pylint --max-line-length=90; \
    )

black: .venv ## use black to format python files
	( \
       . .venv/bin/activate; \
       git ls-files '*.py' |  xargs black --line-length=79; \
    )

black-check: .venv ##  fail if there are formatting propblems
	( \
       . .venv/bin/activate; \
       git ls-files '*.py' |  xargs black --check --line-length=79; \
    )

shellcheck: ## use black to format python files
	( \
       git ls-files 'scripts/*.sh' |  xargs shellcheck --format=gcc; \
    )

unit-test: .venv ## run test that have no external dependencies
	( \
       source .venv/bin/activate; \
       python3 -m pytest -v -m "unit" tests/; \
    )
	node --test "tests/js/**/*.test.js"

unit-update_golden: .venv ## update update golden files with latest results
	( \
       source .venv/bin/activate; \
       python3 -m pytest -v -m "unit" tests/ --update_golden; \
    )

aws-test: .venv ## run test that require aws credentials
	( \
       source .venv/bin/activate; \
       python3 -m pytest -v -m "aws" tests/; \
    )

aws-update_golden: .venv ## update golden files with actual results
	( \
       source .venv/bin/activate; \
       python3 -m pytest -v -m "aws" tests/ --update_golden; \
    )

static: .venv shellcheck black pylint unit-test ##  run all static checks


# Run static-check in github actions (or similar). It should error out if any
# checks fail, which protects the repo from bad pushes
static-check: .venv shellcheck black-check pylint unit-test ## repo branch protection

clean-cache: ## clean python adn pytest cache data
	@find . -type f -name "*.py[co]" -delete -not -path "./.venv/*"
	@find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} \;
	@rm -rf .pytest_cache

git-status: ## require status is clean so we can use undo_edits to put things back
	@status=$$(git status --porcelain); \
	if [ ! -z "$${status}" ]; \
	then \
		echo "Error - working directory is dirty. Commit those changes!"; \
		exit 1; \
	fi

undo_edits: ##  reset changes to HEAD
	git reset HEAD --hard
	git clean -f

node_modules: ## create node_modules/ if it doesn't exist
	bash scripts/update_cdk_libs.sh $(CDK_VERSION)
	$(MAKE) clean-venv

cdk-ls: node_modules .venv ## run cdk ls
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) ls -c app_env=$(app_env); \
    )

cdk-diff: node_modules .venv ## cdk diff a single stack
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) diff $(stack) -c app_env=$(app_env); \
    )

cdk-diff-all: node_modules .venv ## cdk diff all stacks in the envirnment
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) diff --all -c app_env=$(app_env); \
    )

cdk-deploy: node_modules .venv ## cdk deploy a single stack
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	# source the pyenv config script
	# set the local python version. redundant but harmless
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) deploy --require-approval never $(stack) -c app_env=$(app_env); \
    )

cdk-destroy: node_modules .venv ## cdk destroy a single stack
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	# source the pyenv config script
	# set the local python version. redundant but harmless
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) destroy --force $(stack) -c app_env=$(app_env); \
    )

cdk-deploy-all: node_modules .venv ## cdk deploy all stacks in an environment
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	# source the pyenv config script
	# set the local python version. redundant but harmless
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) deploy --all $(stack) -c app_env=$(app_env); \
    )

diff-polls: node_modules .venv ## cdk diff the polls stack and the stacks it depends on
	$(eval CDK := $(shell find . -type f -name cdk))
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       $(CDK) diff '*PollsStack' -c app_env=$(app_env); \
    )

deploy-polls: unit-test node_modules .venv ## run unit tests, then deploy the polls stack (and its dependencies)
	# CDK's default approval prompt stays on so IAM broadening is reviewed
	$(eval CDK := $(shell find . -type f -name cdk))
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       $(CDK) deploy '*PollsStack' -c app_env=$(app_env); \
    )

cdk-bootstrap: node_modules .venv ## bootstrap the default account and region for an environment
	# cdk executable usually: node_modules/aws-cdk/bin/cdk
	# have to be evaluated after the node_modules target
	$(eval CDK := $(shell find . -type f -name cdk))
	# source the pyenv config script
	# set the local python version. redundant but harmless
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
       $(CDK) $(shell bash scripts/cdk_bootstrap.sh) -c app_env=$(app_env); \
    )


dump-poll: .venv ## print one poll's responses as JSON (make dump-poll poll=<poll-id>)
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       PYTHONPATH="." python3 scripts/dump_poll.py $(poll) --app-env $(app_env); \
    )

purge-emails: .venv ## report emails older than N days; add yes=1 to delete them (make purge-emails days=365)
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       PYTHONPATH="." python3 scripts/manage_emails.py --app-env $(app_env) purge --older-than-days $(days) $(if $(yes),--yes,); \
    )

delete-email: .venv ## report records for one address; add yes=1 to delete them (make delete-email email=a@b.co)
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       PYTHONPATH="." python3 scripts/manage_emails.py --app-env $(app_env) delete --email '$(email)' $(if $(yes),--yes,); \
    )

# Names the polls log check needs, read from the stack's own inputs so nothing
# repeats a formula: log group, region, stack, resource prefix, web ACL metric
# name, account number (space separated).
POLLS_NAMES := import sys; from config.settings import get_actual_path; from stack.polls import PollsInput; from stack.site import SiteInput; path = get_actual_path(sys.argv[1]); p = PollsInput.from_config_directory(path); s = SiteInput.from_config_directory(path); print(p.log_group_name(), p.env_setting.default_region, p.stack_name(), p.prefix(), s.prefix() + 'WebACL', p.env_setting.aws_account_number)

fetch-logs: .venv ## download the polls function's log (default 90 days) to .polls-check/handler.jsonl (make fetch-logs days=30)
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       set -euo pipefail; \
       read -r log_group region _ <<< "$$(PYTHONPATH="." python3 -c "$(POLLS_NAMES)" $(app_env))"; \
       mkdir -p .polls-check; \
       start=$$(( ($$(date +%s) - $(or $(days),90) * 86400) * 1000 )); \
       aws logs filter-log-events --region "$$region" --log-group-name "$$log_group" --start-time "$$start" --output json \
         | jq -c -f scripts/jq/polls_log_lines.jq > .polls-check/handler.jsonl.tmp; \
       mv .polls-check/handler.jsonl.tmp .polls-check/handler.jsonl; \
    )

fetch-metrics: .venv ## download daily metrics (default 90 days, UTC days) to .polls-check/metrics.json (make fetch-metrics days=30)
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       source .venv/bin/activate; \
       set -euo pipefail; \
       read -r _ region stack prefix webacl account <<< "$$(PYTHONPATH="." python3 -c "$(POLLS_NAMES)" $(app_env))"; \
       resources=$$(aws cloudformation describe-stack-resources --region "$$region" --stack-name "$$stack" --output json); \
       function=$$(jq -r --arg prefix "$${prefix}SubmitFunction" '[.StackResources[] | select(.ResourceType == "AWS::Lambda::Function" and (.LogicalResourceId | startswith($$prefix))) | .PhysicalResourceId] | if length == 1 then .[0] else error("expected one submit function, found \(length)") end' <<< "$$resources"); \
       distribution=$$(jq -r '[.StackResources[] | select(.ResourceType == "AWS::CloudFront::Distribution") | .PhysicalResourceId] | if length == 1 then .[0] else error("expected one distribution, found \(length)") end' <<< "$$resources"); \
       queries=$$(jq -n -f scripts/jq/polls_metric_queries.jq --arg function "$$function" --arg distribution "$$distribution" --arg account "$$account" --arg webacl "$$webacl"); \
       start=$$(date -u -d "$(or $(days),90) days ago" +%Y-%m-%dT00:00:00Z); \
       end=$$(date -u +%Y-%m-%dT%H:%M:%SZ); \
       mkdir -p .polls-check; \
       aws cloudwatch get-metric-data --region "$$region" --start-time "$$start" --end-time "$$end" --metric-data-queries "$$queries" --output json > .polls-check/metrics.json.tmp; \
       mv .polls-check/metrics.json.tmp .polls-check/metrics.json; \
    )

check-polls: fetch-logs fetch-metrics ## fetch the polls log and metrics, then print one JSON summary of problems (make -s check-polls days=30)
	@jq -n --argjson logs "$$(jq -s -f scripts/jq/polls_log_summary.jq .polls-check/handler.jsonl)" --argjson metrics "$$(jq -s -f scripts/jq/polls_metrics_summary.jq .polls-check/metrics.json)" '{logs: $$logs, metrics: $$metrics.metrics, incomplete_metrics: $$metrics.incomplete}'

discover: .venv ## update environment config data with discovered information
	( \
       source scripts/enable_pyenv.sh; \
       pyenv local $(PYTHON_VERSION); \
       python --version; \
       source .venv/bin/activate; \
	       PYTHONPATH="." python3 -m config.discover $(app_env); \
    )

.PHONY: build static test artifact	
