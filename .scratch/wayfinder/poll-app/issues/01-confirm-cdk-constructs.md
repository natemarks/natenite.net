Status: ready-for-agent
Type: AFK
Blocked by: none

# 01. Confirm the CDK constructs exist in the pinned version

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Local synth and docs checks, no AWS resources. The research read `aws-cdk-lib` 2.273.0 docs but the repo pins 2.260.0, and several decisions depend on specific constructs. Find out now what exists, before building on it.

## Acceptance criteria

- [x] The pinned version is checked for each of these, and the exact API names are recorded as a comment on this issue: the Function URL origin with origin access control; asset directories that follow symlinks; the log-delivery resources (destination, source, delivery) and the property that selects JSON output; Glue table, Athena workgroup and named query constructs; saved Logs Insights query definitions; the Lambda runtime constant to use.
- [x] A throwaway synth confirms that asset content hashes appear in the template for a Lambda code asset and a bucket deployment.
- [x] Node is confirmed available for `make unit-test`, and its version is noted for CI.
- [x] Any missing construct has a written workaround; if a library bump is needed it is proposed as its own change through `make update_cdk_libs`.
- [x] No AWS resources are created and nothing is deployed.

## Blocked by

- None - can start immediately

## User stories addressed

Spec user stories: Enabling work only: 66, 67, 70, 71

## Comments

- 2026-10-16: claimed; spike started. Results are appended below.

### Result (2026-10-16): everything the plan needs exists in `aws-cdk-lib` 2.260.0, with one gap and four implementation notes

Method: introspection of the pinned library (2.260.0, Python 3.12.13) plus a throwaway stack synthesized in a scratch directory outside the repo (Lambda from a symlinked asset directory, Function URL with IAM auth, distribution with S3 and Function URL OAC origins, bucket deployment, log delivery, DynamoDB table). The same stack was synthesized against 2.273.0 in a separate virtualenv for comparison. No AWS resources were created, nothing in the repo changed.

**Constructs confirmed present (API names):**
- Function URL origin with OAC: `aws_cloudfront_origins.FunctionUrlOrigin.with_origin_access_control(lambda_function_url, origin_access_control=...)`; `aws_cloudfront.FunctionUrlOriginAccessControl`; `Signing.SIGV4_ALWAYS`; `FunctionUrlAuthType.AWS_IAM`; `Function.add_function_url`. Synthesizes an OAC of origin type `lambda`, signing `always`, protocol `sigv4`.
- Symlink-following assets: `Code.from_asset(path, follow_symlinks=SymlinkFollowMode.ALWAYS)` and the same on `s3_deployment.Source.asset`. A relative symlink pointing outside the asset directory is materialized as a real directory in the staged asset (verified: `polls/poll1.json` present, not a symlink).
- Log delivery: `aws_logs.CfnDeliverySource` (`name`, `log_type`, `resource_arn`), `CfnDeliveryDestination` (`name`, `delivery_destination_type`, `destination_resource_arn`, **`output_format`**, `delivery_destination_policy`), `CfnDelivery` (`delivery_destination_arn`, `delivery_source_name`, `s3_enable_hive_compatible_path`, `s3_suffix_path`, `record_fields`). `output_format="json"` synthesizes. Whether CloudFront accepts `log_type="ACCESS_LOGS"` and the bucket-policy statements delivery needs are deploy-time facts, left for slice 12.
- `aws_glue.CfnDatabase` and `CfnTable`; `aws_athena.CfnWorkGroup` and `CfnNamedQuery`; `aws_logs.CfnQueryDefinition` (`name`, `query_string`, `log_group_names`, `parameters`, `query_language`).
- Runtime constants `Runtime.PYTHON_3_10` to `PYTHON_3_14`; plan uses `PYTHON_3_12` (matches local Python 3.12.13).
- Also confirmed for later slices: `ddb.Table(deletion_protection=True)`, `Function(reserved_concurrent_executions=..., log_group=...)`, `RetentionDays.ONE_YEAR`, `cloudfront.FunctionRuntime.JS_2_0`, and WAF `CfnWebACL.RateBasedStatementProperty(aggregate_key_type, limit, evaluation_window_sec, scope_down_statement, ...)` with `AndStatementProperty(statements)` and `ByteMatchStatementProperty` for the scope-down.

**The gap (affects slice 03):** in the pinned 2.260.0, the Function URL OAC origin adds only `lambda:InvokeFunctionUrl` for the CloudFront principal. AWS now requires `lambda:InvokeFunction` as well (the installed library's own README says so, "Starting Oct 2025, Function URL invocation will require two permissions"). In 2.273.0 the same code synthesizes both. Options: (a) add the second permission explicitly in the polls stack for 2.260.0 (small, no library change); (b) bump the library first (changes every golden file, so it must be its own change). Recommended: (a), and if the library is bumped later, remove the explicit permission to avoid a duplicate. This corrects the earlier research, which read only the 2.273.0 docs.

**Implementation notes:**
1. **Asset hashes in the template:** four 64-hex hashes appear: the Lambda code `S3Key`, the bucket deployment's `SourceObjectKeys`, and two library-provided ones (the bucket-deployment handler code `S3Key` and the AWS CLI layer `S3Key`). Editing a poll definition reached through the symlink changed only the Lambda code hash. The library-provided hashes change on every `aws-cdk-lib` bump, so the golden-test helper should normalize every 64-hex asset key, not just the project's own.
2. **Relative asset paths:** CDK resolves a relative asset path against the directory the Python process started in, not against a later `os.chdir`. Build asset paths from the project root constant so tests and `cdk` work from any directory.
3. **CLI:** the repo's CDK CLI is 2.1128.1 (from `package.json`), independent of the library pin.
4. **Node for CI:** local Node is v22.23.3; suggest pinning `actions/setup-node` to major version 22 in slice 03's CI change.

Spike scripts lived in the session scratchpad (outside the repo) and are not committed.

### Follow-up (2026-10-16): library bumped to 2.273.0; the gap is closed

The repo owner bumped `aws-cdk-lib` to 2.273.0 (`requirements.txt`) and the CDK CLI to 2.1145.0 (`package.json`), and rebuilt the virtualenv. Checked afterwards:
- Installed in the virtualenv: `aws-cdk-lib` 2.273.0, `constructs` 10.8.1, `jsii` 1.141.0.
- `make unit-test`: all 14 existing tests pass unchanged, so no golden file moved with the bump.
- The earlier comparison synth against 2.273.0 showed the Function URL OAC origin adding both `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction`, so slice 03 does **not** need an explicit second permission (option (a) above is no longer needed).
- All other constructs and notes from the result above hold on 2.273.0 (the spike's comparison run covered symlinked assets, log delivery with JSON output, OAC settings, reserved concurrency, runtime and table protection).
- Note: there is no `make clean` target; the Makefile has `clean-venv` and `clean-cache`.
