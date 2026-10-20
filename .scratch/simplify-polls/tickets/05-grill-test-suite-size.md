---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: test suite size and overlap

## Question

The branch adds about 4,000 lines of tests plus a 1,422-line golden file for
the polls stack: `test_handler.py` (1,179), `test_polls.py` (602),
`lib.test.js` (530), the three script test files, and the access-log query
tests. Given the shape decided by the earlier tickets, which tests earn their
maintenance cost, which overlap (for example assertions that the goldens
already cover), and what should the test strategy be per layer?

CLAUDE.md requires a golden parameter test per stack and per environment;
that stays.

## Resolution

Decided with the human, one branch at a time. Finding: most of the 4,000 test
lines are breadth the spec asks for, not redundancy; the overlap is in four
places, and one test is a build-breaker. Strategy per layer after the earlier
tickets: **infrastructure** = the golden test per stack and environment
(required by CLAUDE.md) plus targeted tests only where they earn it;
**handler** = behaviour tests through one `handle()` call, each behaviour
pinned once; **page logic** = `node --test` over `lib.js` plus the
`MAX_TEXT_CHARS` contract test; **real poll files** = the lint and one
submission test per file, with no test of a poll's content; **owner scripts**
= tests of the destructive behaviour.

1. **Tests that pin real poll files.** Delete
   `test_the_launch_poll_offers_the_four_november_dates_until_the_15th`: it
   asserts the launch poll's exact content and
   `sorted(definitions) == ["nov20267s-in-603"]`, which fails as soon as a
   second poll file is added, so following `POLLS.md`'s "Add a poll" steps
   breaks `make unit-test` and therefore `make deploy-polls`, and it goes
   stale when the poll closes. Merge
   `test_every_bundled_definition_accepts_a_valid_submission` into the
   parametrized `test_every_bundled_poll_accepts_a_valid_submission` and
   delete the loop version and its duplicate helper (`a_valid_answer` against
   `valid_answers_for`). Keep `test_every_poll_definition_in_the_repository_is_valid`
   (the lint that stops a bad poll before deploy). About 55 lines.
2. **Infrastructure tests beyond the golden file** stay only if they protect an
   invariant a blind `make unit-update_golden` could silently erase, cover what
   the golden cannot see, or test logic that turns settings into template
   values. Keep: table retained, deletion-protected, no point-in-time recovery;
   function may only `PutItem`; function URL requires IAM auth; page and
   definitions deployments do not prune each other; the distribution has the
   web ACL attached (reduced from the hostname-certificate-ACL test); log group
   retained; function bundle holds the modules and every definition (the golden
   normalizes asset hashes); reserved concurrency unset and applied when set;
   the rate rule built from `PollsSetting`; the rate rule watches the host and
   path the site serves. Cut: hostname and certificate on the distribution,
   the rewrite-function association, the alias record, `/submit` behaviour and
   no caching, the origin using OAC, the CloudFront invoke permissions, "no
   alarms or notification topics", and in `test_site.py` the default-shape
   rate-rule test and the managed-rule priorities test. About 160 lines. The
   access-log tests and the saved-queries test already leave through tickets
   01 and 06.
3. **Handler logging tests: one assertion per behaviour.** Keep
   `test_no_line_contains_content_and_each_request_logs_exactly_one` as the
   single guard for "no personal data in logs" and delete
   `test_an_email_address_never_reaches_logs_or_other_output` (a subset). Fold
   `requestId` into the accepted-line test and delete
   `test_request_ids_and_yes_no_flags_pass_through` (its other fields are
   removed in ticket 03). Cut the 7-case rejection-logging table to the cases
   with unique log value: bad answer on a real poll, hostile poll ID (no
   log-line injection), closed poll. Update the accepted-line test to the
   trimmed field set from ticket 03. About 85 lines.
4. **Keep `test_handler.py` as one file** (about 1,040 lines after these
   cuts, still over pylint's 1,000-line threshold, so the `too-many-lines`
   disable stays). The topics are already grouped in order, the tests share one
   fixture set (`FakeTable`, `DEFINITIONS`, `post_event`, `submit`, ...) that a
   split would move into a helper module, and ticket 03 kept `handler.py` as
   one file. Revisit past about 1,500 lines.
5. **Leave the rest.** `lib.test.js` (41 tests: signing, browser token and
   storage, retries with backoff, busy message; no Python overlap), the script
   tests (`test_dump_poll.py`, `test_manage_emails.py`: dry-run by default,
   deletes only what it should, never prints an address), `test_polls_page.py`
   (HTML shell guards), `test_limits_contract.py`, the test-helper tests and
   `test_definitions.py` apart from the budget tests. Cut one:
   `test_polls_setting_reads_the_rate_limit_and_leaves_the_reservation_unset`
   restates `polls.json` values that the golden and the kept concurrency test
   already pin (about 12 lines). The sibling
   `test_polls_setting_reads_production_subdomain` stays, matching the
   `EnvironmentSetting` tests.

Totals, counting this ticket together with the removals decided earlier (all
estimates from line counts, not measured after the fact): about 850 of the
roughly 3,950 added test lines leave: `test_polls_access_log_queries.py` (194)
and `test_query_logs.py` (161) as whole files, about 257 from
`test_polls.py`, about 140 from `test_handler.py`, about 60 from
`test_definitions.py`, about 27 from `test_site.py` and about 12 from
`test_settings.py`. The polls golden file also shrinks by the access-log
bucket, delivery, Glue and Athena resources and the saved queries, and shifts
for the pinned log group name. Not added: tests for the new Make targets, jq
files and hostname method (the optional jq fixture test from
[Grill: owner scripts and docs](06-grill-owner-scripts-and-docs.md) is the
only candidate).
