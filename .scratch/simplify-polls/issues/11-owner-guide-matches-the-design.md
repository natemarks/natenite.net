Status: ready-for-agent
Type: AFK
Blocked by: 02, 04, 05, 06, 07, 09, 10

# 11. Owner guide and README match the simplified design

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Make the owner guide and README match the simplified design. The guide keeps what an operator needs and cannot read from the code or `make help`, and points to code or settings for numbers instead of restating them. Remove the command reference table and the README's command block (a link and one sentence remain); replace the definition-rules tables with a short list and a pointer to the example poll; rewrite monitoring around `make check-polls` with the trimmed log fields and the reasons table, replacing the long list of 400-level reasons with "any other 400"; cut the cost-and-limits section to what is not in code; correct every statement the other slices make false (at most two free-text questions, "a poll too big to submit fails here", access logs, saved queries, the removed log fields, the response ID shape). Keep how it fits together, one-time setup, add/change/close/roll back, the `jq` counting recipes and email management. Links to the spec and research are updated in the prune slice. See [Grill: owner scripts and docs](../tickets/06-grill-owner-scripts-and-docs.md), decision 5.

## Acceptance criteria

- [x] Every statement in the guide matches the code after the earlier slices.
- [ ] The guide is about 200 lines. (It is 258, down from 309: see the comment below. Left open for you.)
- [x] No mention of access logs, Athena, saved queries, the removed log fields or the size-budget check remains.
- [x] The README's polls section is a link and one sentence.
- [ ] Following the guide's "add a poll" steps from a clean checkout works. (Steps 1 and 2 were followed on the working tree, not a clean checkout, and work; steps 3 to 5 need an AWS login and are exercised in the deploy slice.)
- [x] `make static` passes.

## Blocked by

- Blocked by [Drop the request-size budget check from poll files](02-drop-the-size-budget-check.md)
- Blocked by [Trim the function's log line and consolidate its logging tests](04-trim-the-log-line.md)
- Blocked by [Timestamp-plus-random response IDs](05-timestamp-response-ids.md)
- Blocked by [Remove the access-log layer](06-remove-the-access-log-layer.md)
- Blocked by [Pin the log group name and drop the saved queries](07-pin-log-group-and-drop-saved-queries.md)
- Blocked by [Log check part 1: errors and rejections from the function's log](09-log-check-errors-and-rejections.md)
- Blocked by [Log check part 2: daily metrics](10-log-check-daily-metrics.md)

## User stories addressed

Spec user stories: 19, 20, 21

## Comments

Done except two criteria (uncommitted): `POLLS.md` rewritten, the polls
section of `README.md` cut to one sentence with the link.

- **Length: 258 lines, not about 200.** The earlier estimate was made before
  the new check section existed. The command table, the definition-rules
  tables, the access-log and saved-query sections, the long 400-level list and
  most of the cost section are gone (309 down to 258), but what remains is the
  content the decisions said to keep: how it fits together, setup,
  add/change/close/roll back, the response and `jq` recipes, email management,
  plus the new check section (42 lines). The code blocks and spacing in those
  account for most of the length. To get nearer 200 something kept would have
  to go; candidates, if you want that: the `jq` recipes (about 8 lines), the
  email read snippet (about 6), the "Remove a response" snippet (about 11), the
  reasons table (about 15). I did not cut them.
- **What changed in the guide:** the command reference table removed (`make
  help` covers it); the definition tables replaced by one paragraph and a
  pointer to the example poll and the unit tests' messages; monitoring
  rewritten around `make -s check-polls` (how to read `logs`, `metrics` and
  `incomplete_metrics`, the metric series, the trimmed log fields, the log
  group name); the reasons table with "any other 400" in place of the 12-name
  list; the cost section reduced to what is kept, the cost, and pointers to
  where the limits live (no numbers repeated, so the Lambda concurrency quota
  the old text stated is gone; the note on `PollsSetting` explains it); the
  example response shows the new ID shape; step 2 of "add a poll" no longer
  promises a size check, and step 5 says what to do if a test submission
  fails; "Remove a response" became a real heading so its link works.
- **Checked against the code:** every `make` target named exists (`make help`);
  the reasons and statuses match the handler's; the log fields match the
  trimmed line; the limits point to `limits.py`, `polls.json` and the
  settings note; none of these terms remains: access logs, Athena, saved
  queries, the removed log fields, the size budget, the old ID shape.
- **Following the steps:** a second poll written from the guide's format
  paragraph passes `make unit-test`; four mistakes the guide names (duplicate
  option, rating range too wide, bad closing time, id different from the file
  name) each fail with a message that names the file and states the rule. The
  throwaway file is removed. Not done: steps 3 to 5 (`diff-polls`, deploy, the
  live page). My AWS login had expired by this session, and a diff today would
  include this whole refactor anyway.
- **Statements worth a glance because I could not check them here:** "about $1
  a month for the firewall rule" (from the earlier verified pricing, not
  re-checked); the log group name `/natenite/production/polls/submit` exists
  only after the deploy slice; the firewall console's sampled requests (from
  the shared ACL's configuration, which keeps them enabled).
- **Two claims I deliberately did not make** because they were never proven:
  that the CloudFront 4xx percentage includes firewall blocks (it does include
  the function's rejections), and that adding a poll changes only the poll
  assets in `diff-polls`.
- `make static` and `make static-check` exit 0: pylint 10.00/10, 267 Python
  tests, 41 Node tests. The links to the spec and research in `POLLS.md` still
  point at the old paths; the prune slice moves them.
