# PRD: simplify the polls implementation

Source of every decision below: the closed tickets of this effort's map
(`map.md`, `tickets/`). Each decision links back to its ticket for the
rationale and the alternatives that were rejected.

## Problem Statement

The polls app on the `research/poll-app` branch works, but it is expensive to
maintain for a single owner running a handful of small polls. About 11,000
lines were added across three runtimes (a Python function, a plain JavaScript
page and CDK infrastructure). A large share of that is machinery nobody reads
or needs:

- Three overlapping ways to check on the polls (CloudFront access logs queried
  through Athena, saved Logs Insights queries, and an owner script that reruns
  the Athena queries), none of which has seen real traffic. The owner only needs
  to see blocked or throttled traffic when something fixable, such as the
  firewall configuration, is causing it.
- The owner has no terminal way at all to read the function's own log, which is
  the main source for identifying and troubleshooting problems. The existing
  script only ever read the access logs.
- A worst-case request-size check on poll files that guards a failure the owner
  would see on the first test submission, with its own constants and tests.
- A hand-rolled bit-level encoder for response identifiers, and log fields that
  nothing reads.
- The polls hostname formula written in two places, and a Site stack that knows
  about polls settings.
- About 4,000 lines of tests, some overlapping the golden files or each other,
  and one test that fails the build as soon as a second poll file is added,
  which is exactly what the documented "add a poll" steps tell the owner to do.
- An owner guide and a README that already contradict the planned design, and
  about 3,500 lines of planning documents, partly wrong, that agents are
  directed to read.

The owner wants the app to be easier to maintain without changing what
respondents see and without revisiting the hosting architecture.

## Solution

Simplify in place, keeping the architecture fixed (a Lambda function URL behind
CloudFront with origin access control, one on-demand DynamoDB table, the shared
web ACL). Remove the machinery above and replace the log tooling with one small,
terminal-friendly check:

- Drop the entire CloudFront access-log layer and accept the blind spot. The
  existing firewall and function metrics cover the cases the owner can act on.
- Give the owner one command that downloads the function's log and a few
  daily metrics for the last 90 days into a local, git-ignored folder and prints
  a summary of problems: errors, rejections by reason, and metric totals per
  day. The same raw files can be searched again with stored queries, and an
  agent session can run it too.
- Trim the function's log line to the fields something reads, simplify response
  identifiers, drop the size-budget check on poll files, and give the polls
  hostname a single definition.
- Cut the test suite to what earns its keep, fix the build-breaking test, and
  add one small test for the new summary.
- Trim the owner guide and README to what the code and `make help` cannot say,
  and prune the planning documents after launch, keeping the spec and the
  research the architecture decision cites.

Respondents see no change.

## User Stories

Owner (running polls):

1. As the poll owner, I want one command that gathers the last 90 days of the
   function's log and key metrics and prints a summary, so that I can find out
   whether anything is wrong without opening the AWS console.
2. As the poll owner, I want the summary to list every error-level log line, so
   that I can see failures on our side first.
3. As the poll owner, I want rejections counted by reason, so that I can tell a
   steady stream of one reason, which means the page and a poll disagree, from
   ordinary visitor mistakes.
4. As the poll owner, I want daily totals of firewall blocks by rule, so that I
   can tell when a firewall configuration is turning away real people.
5. As the poll owner, I want daily totals of function errors and throttles, so
   that I can see when a concurrency or capacity limit is being hit.
6. As the poll owner, I want the distribution's error rate per day, so that I
   can see failures that never reach the function.
7. As the poll owner, I want the log and the metrics downloaded separately as
   well as together, so that I can refresh one without the other.
8. As the poll owner, I want the downloads kept in a git-ignored folder, so that
   I can search them repeatedly and offline without committing log data.
9. As the poll owner, I want the window to default to 90 days and be adjustable,
   so that routine checks are short and an investigation can go further back.
10. As the poll owner, I want the function's log group to have a fixed, known
    name, so that commands can find it without a lookup.
11. As the poll owner, I want a logged request-size field kept on every line, so
    that a request rejected for being too large tells me whether a poll outgrew
    the limit or someone sent junk.
12. As the poll owner, I want the log to carry no email address, answer text,
    browser token or token hash, so that a downloaded copy is safe to keep and
    share.
13. As the poll owner, I want to read a poll's stored responses with the existing
    command, unchanged, so that results keep working through the refactor.
14. As the poll owner, I want to purge old email addresses and delete one
    address with the existing commands, still dry-run by default, so that
    retention and removal requests keep working.
15. As the poll owner, I want to add a second poll by following the owner guide
    without the unit tests failing, so that the documented steps work.
16. As the poll owner, I want a poll file with a typo, a duplicate id, a bad
    rating range or a malformed closing time to fail before deploy, so that a
    mistake does not become a runtime error.
17. As the poll owner, I want a poll that is too large to submit to show up as a
    clear rejection with its size on the first test submission, so that I can
    fix it without a build-time size calculator.
18. As the poll owner, I want response identifiers that sort by submission time
    and are readable in the results output, so that results come back in order
    and I can recognise when a response arrived.
19. As the poll owner, I want a short owner guide that covers how to add,
    change, close and roll back polls, read results, manage emails and run the
    check, so that I can operate the app from one page.
20. As the poll owner, I want the guide to point at the example poll and the
    checker's own messages instead of restating every rule, so that it does not
    drift when a rule changes.
21. As the poll owner, I want the guide's statements about limits and log fields
    to be correct, so that I am not misled when troubleshooting.
22. As the poll owner, I want the rate-limit setting to keep flowing from the
    polls settings into the firewall rule, so that tuning it stays a one-line
    change.
23. As the poll owner, I want no new always-on cost, so that the app stays at
    about a dollar a month plus cents.

Respondent:

24. As a respondent, I want the poll page, submit, retry, closed and
    already-answered behaviour to be exactly as before, so that nothing I rely
    on changes.
25. As a respondent, I want a message that tells me my answers were saved when
    only my email address could not be stored, so that I know whether to retry.
26. As a respondent, I want an over-long free-text answer to count down from the
    same number the server enforces, so that I am not told too late.

Maintainer and agent:

27. As a maintainer, I want one definition of the polls hostname, so that the
    Site and Polls stacks cannot disagree.
28. As a maintainer, I want the free-text limit mirrored between the function
    and the page to be guarded by a test, so that drift is caught.
29. As a maintainer, I want each log behaviour pinned by exactly one test, so
    that changing the log shape means editing one place.
30. As a maintainer, I want "no personal data in logs" guarded by one
    comprehensive test across accepted, rejected and failed requests, so that
    the privacy rule has a single obvious guard.
31. As a maintainer, I want infrastructure tests beyond the golden file only for
    invariants a blind golden update could erase, things the golden cannot see,
    and settings-to-template logic, so that infrastructure changes do not touch
    several overlapping tests.
32. As a maintainer, I want the golden test per stack and environment kept, so
    that template drift is always visible.
33. As a maintainer, I want one test per real poll file that checks the function
    accepts a valid submission, so that the poll checker and the function cannot
    silently disagree.
34. As a maintainer, I want no test that pins a poll's wording, dates or the
    exact set of poll files, so that normal poll changes never fail the build.
35. As a maintainer, I want the retained data safeguards (table retention,
    deletion protection, no point-in-time recovery, write-only access for the
    function, IAM-authenticated function URL, firewall attached) to stay
    asserted, so that a template regeneration cannot erase them unnoticed.
36. As a maintainer, I want a small fixture test for the log summary, so that a
    typo in the check surfaces in the normal test run and not the first time I
    need it.
37. As an agent session, I want to run the check from the terminal and read its
    output, so that I can help troubleshoot without the console.
38. As an agent session, I want the planning documents to describe the current
    design, so that I am not misled by stale ones.
39. As a future reader, I want the requirements and the research behind the
    architecture decision to live with the reference docs, so that I can see why
    the app is built this way.
40. As a future reader, I want a short note on the spec listing what has changed
    since it was written and where to find the original planning files, so that
    the record stays honest without a rewrite.
41. As a maintainer, I want the planning files recoverable from a tag even if
    the branch is squash-merged and deleted, so that pruning loses nothing.
42. As a maintainer, I want every deploy of the refactor to be previewed before
    it is applied, so that replacements of retained resources are never a
    surprise.

CI:

43. As the CI gate, I want the static-check target to run the same tests as the
    local target, including the new summary test, so that nothing is checked
    only on one machine.

## Implementation Decisions

Each item names the ticket that holds the rationale.

**Fixed constraints** (map Notes): the hosting architecture (decision record
0001) is unchanged; respondent-visible behaviour is unchanged; the static
checks pass, including a golden parameter test per stack and environment.

**Observability** ([observability layers](tickets/01-grill-observability-layers.md),
amended by [owner scripts and docs](tickets/06-grill-owner-scripts-and-docs.md)):
- Remove the access-log layer completely: the delivery and its bucket and
  policy, the table and database definitions, the query workgroup and its saved
  queries, the module that holds them, and the owner script that ran them with
  its Make target and documentation.
- The function's log group stays, kept 365 days and retained when the stack is
  deleted, and now has a fixed name chosen in the stack so tooling can find it.
- Remove the saved Logs Insights queries. Each routine question is defined once,
  in the local summary.
- The blind spot (no long-term, address-level record of blocked or throttled
  traffic, no page-view record) is accepted. Blocked requests remain visible
  through the firewall's per-rule metrics and sampled requests, and throttles
  through the function's own metrics.

**Log check tooling** (new, [owner scripts and docs](tickets/06-grill-owner-scripts-and-docs.md)):
- Three Make targets with a 90-day default window that takes a days argument:
  fetch the function log, fetch daily metrics, and a combined check that runs
  both and prints one summary. No new Python.
- The log fetch writes the function's log lines, one JSON object per line, to
  a git-ignored working folder. The metric fetch reads a stored metric query
  definition covering firewall blocked requests by rule, function errors and
  throttles, and the distribution's error rate, all at daily resolution (finer
  resolution is only retained for a short time), and writes one JSON file.
- The summary is a stored jq program with a stable contract: input is the log
  lines, output is a JSON summary of error-level lines and rejection counts by
  reason; a second stored program summarises the metrics file per day.
- The exact metric names and dimensions, notably for firewall metrics on a
  CloudFront-scoped web ACL, are unverified and must be confirmed while
  building.
- The tooling reads the log and metrics only; it changes nothing in AWS.

**Submit function** ([handler structure](tickets/03-grill-handler-structure.md)):
- Log line fields become: level, outcome, status, reason, poll ID, response ID,
  body size, request ID, and for failures the error type and error code. Removed:
  the CloudFront request ID, the two has-email and has-token flags, the event
  timestamp field and the constant event name. The rule that no line ever holds
  email, answer text, browser token or token hash stays.
- The internal facts record shrinks to poll ID, response ID, request ID and the
  failure; the validation step stops recording the two flags.
- The collaborator wiring (a services tuple, an injectable clock, the split
  between a testable entry point and the deployed one) is left as is. The file
  is not split.
- Response identifiers become a UTC timestamp with microseconds followed by a
  separator and 64 random bits as hex. They still sort by submission time and
  remain injectable for tests. Nothing parses the identifier; the results script
  and the email script match only the record-type prefixes.

**Poll checks and limits** ([poll definition rules](tickets/02-grill-poll-definition-rules.md)):
- Keep the structural checks on poll files (id and file name, version, title,
  closing time, questions, options, rating bounds).
- Remove the worst-case size computation, its check and the reserved-bytes
  constant. The shared limits module is left with the body limit, the text
  limit and the email limit.
- Keep the one mirrored limit (free-text length) in both the function and the
  page, guarded by the existing contract test. Keep the bundling of poll files
  into the function through the symlinked folder.

**Stacks and settings** ([stack layout](tickets/04-grill-stack-layout.md)):
- The polls rate rule stays on the shared ACL in the Site stack. A separate ACL
  was rejected for its recurring cost.
- The polls hostname is computed by one method on the polls settings, used by
  both the Site input and the Polls input.
- The Polls stack stays a single stack with a linear constructor. No new
  constructs, because moving existing resources under new construct paths would
  change their logical IDs and risk replacing the retained table and bucket.

**Owner scripts** ([owner scripts and docs](tickets/06-grill-owner-scripts-and-docs.md)):
- Keep the results script and the email management script and their Make targets
  unchanged; the one script-to-script import is left alone.

**Docs** ([owner scripts and docs](tickets/06-grill-owner-scripts-and-docs.md),
[planning docs](tickets/07-grill-planning-docs-after-build.md)):
- The owner guide keeps what an operator needs and cannot read from the code or
  `make help`; numbers that live in code or settings are pointed to, not
  restated. Remove the command table; replace the rules tables with a short list
  and a pointer to the example poll; rewrite monitoring around the check;
  replace the long list of 400-level reasons with "any other 400"; cut the cost
  and limits section to what is not in code; correct every statement the other
  decisions make false. Target about 200 lines from 309.
- The README's polls section becomes a link and one sentence.
- Move the spec and the two research notes that the architecture decision
  record cites into the reference docs folder, update every link to them, and
  add a "Changes since this spec" note at the top of the spec. Delete the other
  planning files after launch verification, tag the branch tip first, and update
  the one sentence in the tracker doc that names the old effort directory.
  Delete this effort's own folder once the refactors ship.
- No change to the glossary, the architecture decision record or the project
  instructions.

**Sequencing constraints:**
- Update the launch verification issue and the build plan to the simplified
  design before launch verification runs: remove the access-log checks, add a
  smoke test that the check runs and returns a summary.
- Delete the planning files only after launch verification passes.
- Before the response-identifier change ships, confirm the deployed table holds
  no responses worth keeping, or clear it: old and new identifiers sort wrongly
  against each other.
- Before the fixed log group name ships, check whether the stack is deployed;
  the rename creates a new group and the retained old group keeps earlier lines.

## Testing Decisions

A good test here drives external behaviour (a request through the function's
entry point and the records and log line that result, a template property that
matters, a command's output) and does not pin implementation structure or
restate data that another test already pins. Each behaviour is pinned once.
Details and the keep and cut lists are in
[test suite size and overlap](tickets/05-grill-test-suite-size.md).

Modules and what is tested:
- **Submit function:** behaviour tests through the single entry point stay,
  including each question type, the email and token records, closing, and
  sortable response identifiers. The logging tests are trimmed to one assertion
  per behaviour: the accepted line with the new field set, the rejection cases
  with unique log value (bad answer on a real poll, a hostile poll ID that must
  not inject a log line, a closed poll), the oversize body logged by size, the
  lost email, the unexpected failure logged by error kind only, and one
  comprehensive test that no personal data appears in any line. The test file
  stays a single file.
- **Poll files:** keep the lint over every real poll file, and one parametrized
  test per real poll file that a valid submission is accepted. Delete the test
  that pins the launch poll's content and the exact set of files, and the
  duplicate loop version of the submission test. Remove the tests of the
  size-budget check.
- **Mirrored limit:** keep the contract test.
- **Polls and Site stacks:** keep the golden test per stack and environment.
  Beyond it keep only: the table is retained, deletion-protected and without
  point-in-time recovery; the function may only put items; the function URL
  requires IAM authentication; the page and definitions deployments do not prune
  each other; the distribution has the web ACL attached; the log group is
  retained (updated for the fixed name); the function bundle holds the modules
  and every definition; reserved concurrency is unset and applied when set; the
  rate rule is built from the polls settings; the rate rule watches the host and
  path the site serves. Delete the tests that restate golden properties, the
  access-log tests and the saved-query test. Remove the one settings test that
  restates configuration values.
- **Log check summary (new):** a small fixture test runs the stored jq programs
  over a handful of fixture lines (accepted, rejected with several reasons,
  failed with an error kind) and a small metrics fixture, and asserts the
  summary. It runs in the normal unit-test gate. The CI runner image is expected
  to provide jq, which is unverified; add an install step to the workflow if it
  does not.
- **Owner scripts, page logic and page shell:** unchanged. The destructive
  script tests, the Node tests of the page library and the HTML shell guards
  stay.

Prior art: the entry-point tests with an in-memory table and fixed clock, the
golden stack tests with normalised asset hashes, the parametrized
per-poll-file tests, and the existing contract test between the function and
the page.

Expected effect, from line counts and not measured afterwards: about 850 of
roughly 3,950 added test lines go, and the polls golden file shrinks by the
access-log, query and delivery resources and shifts for the fixed log group
name.

## Out of Scope

- Changing the hosting architecture: compute, storage or routing.
- Any change a respondent can see.
- Moving the polls rate rule out of the Site stack, or giving Polls its own ACL.
- Splitting the Polls stack into constructs, splitting the submit function or
  its test file, or merging the owner scripts into one tool.
- Filtering or normalising log events across sources (the observability data
  model), already ruled out of the original effort.
- Restoring long-term, address-level records of blocked traffic.
- Rewriting the original spec to match the final code.
- Authoring poll questions, and the privacy notice wording, both on the launch
  checklist.
- Ordering and slicing the refactors; that is the next step after this document.

## Further Notes

- Unverified items to confirm during the build: the metric names and dimensions
  for firewall metrics on a CloudFront-scoped ACL, whether CI's runner image
  provides jq, and (from the research) the retention figures other than hourly
  metric data being kept 455 days.
- All size and line-count figures in this document are estimates from reading
  the code, not measurements taken after the changes.
- Tickets that hold the detail: observability layers, poll definition rules and
  shared limits, submit handler structure, stack layout and WAF rule ownership,
  owner scripts and docs, test suite size and overlap, planning docs after the
  build (all under this effort's `tickets/`).
- Amendments: the saved Logs Insights queries kept by the observability ticket
  were later dropped by the owner scripts ticket, and the inlining of those
  queries in the stack layout ticket is moot.
