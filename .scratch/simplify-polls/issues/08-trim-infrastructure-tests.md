Status: ready-for-agent
Type: AFK
Blocked by: 03, 07

# 08. Trim infrastructure tests to the kept invariants

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Cut the infrastructure tests beyond the golden file to the kept set. Keep: table retained, deletion-protected and without point-in-time recovery; function may only put items; function URL requires IAM authentication; page and definitions deployments do not prune each other; the distribution has the web ACL attached (reduced from the hostname-certificate-ACL test); log group retained; function bundle holds the modules and every definition; reserved concurrency unset and applied when set; the rate rule built from the polls settings; the rate rule watches the host and path the site serves. Delete: hostname and certificate on the distribution, the rewrite-function association, the alias record, `/submit` behaviour and no caching, the origin using origin access control, the CloudFront invoke permissions, "no alarms or notification topics", the Site default-shape rate-rule test, the managed-rule priorities test, and the settings test that restates configuration values. Keep the golden test per stack and environment. See [Grill: test suite size and overlap](../tickets/05-grill-test-suite-size.md), decisions 2 and 5.

## Acceptance criteria

- [x] Only the kept tests remain; each deleted test's property is still pinned by the golden file.
- [x] The golden test per stack and environment is unchanged.
- [x] A quick check shows each kept invariant test fails if its property is removed from the template (shown in the PR).
- [x] `make static` passes.

## Blocked by

- Blocked by [One definition of the polls hostname](03-one-polls-hostname.md)
- Blocked by [Pin the log group name and drop the saved queries](07-pin-log-group-and-drop-saved-queries.md)

## User stories addressed

Spec user stories: 22, 31, 32, 35

## Comments

Done (uncommitted) in `tests/unit/stack/test_polls.py`,
`tests/unit/stack/test_site.py` and
`tests/unit/config/settings/test_settings.py`. No source or golden file changed
in this slice.

- **Deleted (test_polls.py, 7 tests):** hostname and certificate on the
  distribution (replaced by `test_the_distribution_is_protected_by_the_shared_web_acl`,
  which asserts only that the web ACL is attached), the rewrite-function
  association, the alias record, `/submit` behaviour and no caching, the origin
  using origin access control, the CloudFront invoke permissions (two
  parametrized cases), and "no alarms or notification topics".
- **Deleted (test_site.py, 2):** the default-shape rate-rule test and the
  managed-rule priorities test. **Deleted (test_settings.py, 1):** the test of
  the rate limit and window values.
- **Kept:** the golden test per stack and environment; table retained and
  protected; function may only put items; function URL requires IAM; deployments
  do not prune each other; the web ACL is attached; log group fixed name,
  365 days, retained; function bundle contents; concurrency unset and applied;
  both rate-rule tests; the settings test that reads the subdomain.
- **Each kept invariant test fails when its property is removed** (a mutation
  run, 17 of 17 caught, source restored after each): table deletion protection
  off, removal policy destroy, point-in-time recovery on; function granted
  read/write instead of put; function URL without auth; page deployment without
  its exclusion and without prune; distribution without a web ACL; log group at
  30 days, removed on delete, generated name; bundle without following
  symlinks; concurrency setting ignored, and hard-coded; rate rule with the
  wrong path, hard-coded limit and hard-coded host.
- **Each deleted test's property is still pinned by the golden file** (5 of 5
  mutations caught by `test_polls_stack_actual` alone): alias record elsewhere,
  `/submit` cacheable, rewrite function mapping to another page, a changed
  distribution hostname, certificate dropped.
- `make static` and `make static-check` exit 0: pylint 10.00/10, 250 Python
  tests (260 before: 7 functions with one doubled by parametrization, replaced
  by 1, plus 2 and 1 elsewhere) and 41 Node tests.
- The mutation scripts were throwaway and live only in the session scratch
  space; they are not part of the repo.
