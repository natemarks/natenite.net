Status: ready-for-agent
Type: AFK
Blocked by: none

# 06. Remove the access-log layer

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Remove the CloudFront access-log layer end to end: the log delivery (source, destination, delivery) and its bucket and bucket policy, the Glue database and table, the Athena workgroup and saved queries, the module that holds them, the owner script that ran those queries with its tests and Make target, and the tests of all of these. Regenerate the Polls golden file and read the diff. The owner guide and README are corrected in the docs slice. See [Grill: observability layers](../tickets/01-grill-observability-layers.md), decision 1.

## Acceptance criteria

- [x] The synthesized Polls template has no log delivery, log bucket, Glue or Athena resources; the golden diff shows only removals and the unchanged table, function, distribution and ACL resources are untouched.
- [x] No code imports the removed module; the query script, its Make target and its tests are gone, and `make help` no longer lists the target.
- [x] The access-log tests are removed.
- [x] No new always-on cost is added.
- [x] `make static` passes.

## Blocked by

None - can start immediately

## User stories addressed

Spec user stories: 23, 35

## Comments

Done (uncommitted). Files: `stack/polls.py`, `Makefile`,
`tests/unit/stack/test_polls.py`, the Polls golden file, and four deleted files
(`stack/polls_access_log_queries.py`, `scripts/query_logs.py`,
`tests/unit/stack/test_polls_access_log_queries.py`,
`tests/unit/scripts/test_query_logs.py`).

- **Stack:** removed the delivery method and its call, the module import and
  the now-unused IAM import. The saved Logs Insights queries and the log group
  are untouched (the next slice handles them).
- **Tests:** removed the four access-log tests and their helper from
  `test_polls.py`. `test_there_are_no_alarms_and_no_notification_topics` stays;
  the infrastructure-tests slice removes it.
- **Golden diff:** 490 deletions, no additions, only the Polls golden changed.
  Resource types removed: 3 Athena named queries, 1 Athena workgroup, 1 Glue
  database, 1 Glue table, the log delivery, delivery destination and delivery
  source, 1 S3 bucket and 1 bucket policy. The other 29 resources are
  identical, and Outputs and Parameters are unchanged. No new resources, so no
  new always-on cost.
- `make help` no longer lists `query-logs`; no code references the removed
  module or script.
- `make static` and `make static-check` exit 0: pylint 10.00/10, 261 Python
  tests (280 before, minus the removed tests) and 41 Node tests.
- **Repo quirk:** the Makefile finds Python files with `git ls-files`, so a
  deleted file must be staged (`git rm`) or black fails on the missing path.
  The four deletions are staged; nothing is committed.
- **For the deploy slice:** the removed log bucket was defined with a
  retain-on-delete policy, so if the stack has ever been deployed the real
  bucket stays behind in the account (and may hold CloudFront logs with client
  IP addresses). Added to the deploy slice's checklist.
- Not touched: the owner guide and README still describe `make query-logs` and
  the access logs; the owner-guide slice corrects them.
