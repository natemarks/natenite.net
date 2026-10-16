Status: ready-for-agent
Type: AFK
Blocked by: none

# 01. Confirm the CDK constructs exist in the pinned version

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Local synth and docs checks, no AWS resources. The research read `aws-cdk-lib` 2.273.0 docs but the repo pins 2.260.0, and several decisions depend on specific constructs. Find out now what exists, before building on it.

## Acceptance criteria

- [ ] The pinned version is checked for each of these, and the exact API names are recorded as a comment on this issue: the Function URL origin with origin access control; asset directories that follow symlinks; the log-delivery resources (destination, source, delivery) and the property that selects JSON output; Glue table, Athena workgroup and named query constructs; saved Logs Insights query definitions; the Lambda runtime constant to use.
- [ ] A throwaway synth confirms that asset content hashes appear in the template for a Lambda code asset and a bucket deployment.
- [ ] Node is confirmed available for `make unit-test`, and its version is noted for CI.
- [ ] Any missing construct has a written workaround; if a library bump is needed it is proposed as its own change through `make update_cdk_libs`.
- [ ] No AWS resources are created and nothing is deployed.

## Blocked by

- None - can start immediately

## User stories addressed

Spec user stories: Enabling work only: 66, 67, 70, 71
