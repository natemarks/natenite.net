---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: stack layout and WAF rule ownership

## Question

`stack/polls.py` (392 lines) builds the bucket, table, log group, function,
CloudFront distribution, DNS record, access-log delivery and two bucket
deployments in one `__init__` plus a helper. `stack/site.py` now takes
`PollsSetting` and owns the polls submit rate rule on the shared ACL.

Decide how the stack should be organised so each change touches one obvious
place: split into constructs, leave as one stack, and whether the rate rule
and its settings belong in Site or Polls. Blocked by the observability
decision because it changes how much of `polls.py` is log plumbing.

## Resolution

Decided with the human, one branch at a time. Facts: after
[Grill: observability layers](01-grill-observability-layers.md) removes the
access-log layer, `stack/polls.py` drops from 392 to roughly 270 lines, one
linear `__init__` of about 170 lines, the same shape as the repo's other
stacks. The coupling cost is concentrated in `site.py`: the polls rate rule
(about 75 lines with `_byte_match`), `PollsSetting` inside `SiteInput`, 149
added test lines, and the polls hostname formula written twice
(`SiteInput.polls_fqdn()` and `PollsInput.fqdn()`).

1. **Keep the polls rate rule in the Site stack.** The polls distribution
   reuses the Site stack's web ACL, and a rule cannot be added to another
   stack's ACL after the fact, so moving it means giving Polls its own ACL.
   Prices verified in research/06 (us-east-1 Price List API): $5.00 per
   ACL-month and $1.00 per rule-month, so a rate-rule-only ACL is about $6 a
   month and one with both managed groups about $8, against about $1 a month
   now for the rule on the shared ACL. Rejected: a separate ACL (roughly $60
   to $85 a year more, always on, against the standing preference to avoid new
   always-on spend, to remove a coupling that only shows up as a Site diff when
   the rate limit changes). Accepted cost: tuning the polls rate limit
   redeploys the stack that serves the main site.
2. **One polls hostname method, in one place.** A single method on
   `PollsSetting` computes `{subdomain}.{default_fqdn}`; `SiteInput` and
   `PollsInput` both call it. This was chosen as the implementation of
   decision 1 and not put to the human separately.
3. **Keep `PollsStack` as one stack; tidy the saved queries in place.** No
   new constructs. With two saved queries left, replace `SAVED_QUERIES` and
   its loop (logical IDs derived through
   `name.split('/')[1].title().replace('-', '')`) with two plain
   declarations. Rejected: splitting into response-store, submit-function and
   poll-site constructs. The tests and golden file assert on the stack
   template, so nothing becomes easier to test, the other stacks are single
   linear `__init__` bodies and `CLAUDE.md` describes one input class plus one
   stack class per module, and moving existing resources under new construct
   paths changes their CloudFormation logical IDs. If the stack has been
   deployed that would replace resources, including the DynamoDB table (fixed
   table name, deletion protection) and the S3 bucket, unless every moved
   resource gets an `override_logical_id`, which adds more code than the split
   removes. Revisit only if the stack grows well past 400 lines.

Consequences for other tickets:

- [Grill: test suite size and overlap](05-grill-test-suite-size.md): the
  access-log tests in `test_polls.py` leave with the code (decision in ticket
  01); `test_the_routine_check_queries_are_saved_against_the_function_log_group`
  must follow the two remaining queries. The Site rate-rule tests in
  `test_site.py` stay. No construct-level tests are introduced.
- [Grill: owner scripts and docs](06-grill-owner-scripts-and-docs.md):
  `dump_poll.py` imports `PollsInput` from `stack/polls.py` only to get
  `table_name()`, deliberately making the stack's input class the single
  source for the table name. That coupling is untouched here.

## Amendment

The inlining of the two saved queries in decision 3 is moot:
[Grill: owner scripts and docs](06-grill-owner-scripts-and-docs.md) drops them.
The log group gets a pinned name instead. Decisions 1, 2 and the one-stack
choice stand.
