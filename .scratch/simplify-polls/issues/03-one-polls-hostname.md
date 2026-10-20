Status: ready-for-agent
Type: AFK
Blocked by: none

# 03. One definition of the polls hostname

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Compute the polls hostname (`<subdomain>.<default fqdn>`) in one method on the polls settings and have both the Site input and the Polls input call it, removing the formula that is written twice. No template changes. See [Grill: stack layout and WAF rule ownership](../tickets/04-grill-stack-layout.md), decision 2.

## Acceptance criteria

- [x] The hostname formula exists in exactly one place; both inputs use it.
- [x] The Site and Polls golden files are unchanged.
- [x] The test that builds the rate rule from custom polls settings (a different subdomain) still passes.
- [x] `make static` passes.

## Blocked by

None - can start immediately

## User stories addressed

Spec user stories: 22, 27

## Comments

Done (uncommitted). This slice touches three files: `config/settings.py`,
`stack/polls.py` and `stack/site.py`.

- Added `PollsSetting.fqdn(default_fqdn)`, which returns
  `<subdomain>.<default_fqdn>`. `PollsInput.fqdn()` and `SiteInput.polls_fqdn()`
  are now one-line calls to it (kept as methods because the stacks call them,
  like `PollsInput.table_name()`).
- The formula appears once in the code (`grep` for `.subdomain` outside tests
  finds only the new method).
- No golden file changed and the gate ran without `--update_golden`;
  `test_the_rate_rule_is_built_from_the_polls_settings` (subdomain `vote`)
  still passes.
- No new test added, as decided in the test-suite ticket: the method is
  covered by the golden files and the custom-subdomain test.
- `make static` exits 0: black unchanged, pylint 10.00/10, 284 Python tests
  and 41 Node tests pass.
