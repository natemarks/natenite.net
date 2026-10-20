Status: ready-for-agent
Type: AFK
Blocked by: 06, 09

# 12. Update the launch-verification issue and build plan

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Before launch verification runs, update the earlier effort's launch-verification issue and build plan to the simplified design: remove the access-log checks (the open question about whether firewall blocks appear as 403s in the CloudFront logs, and the log-delivery and Athena smoke tests), mark the earlier log-delivery and Athena issues as superseded, and add a smoke test that `make check-polls` runs against production and returns a summary. See [Grill: planning docs after the build](../tickets/07-grill-planning-docs-after-build.md), decision 3.

## Acceptance criteria

- [x] The launch-verification issue and build plan contain no check for a component that no longer exists.
- [x] The earlier log-delivery and Athena issues carry a superseded note.
- [x] A smoke test for `make check-polls` is added to the launch checklist.
- [x] No other launch criteria are changed.

## Blocked by

- Blocked by [Remove the access-log layer](06-remove-the-access-log-layer.md)
- Blocked by [Log check part 1: errors and rejections from the function's log](09-log-check-errors-and-rejections.md)

## User stories addressed

Spec user stories: 38

## Comments

Done (uncommitted, after the refactor and the planning files were committed as
`c658798` and `9eae902`). Files, all under `.scratch/wayfinder/poll-app/`:
`issues/15-launch-verification.md`, `build-plan.md`,
`issues/12-cloudfront-logs-to-s3.md`, `issues/13-athena-over-cloudfront-logs.md`
and `issues.json`.

- **Launch-verification issue:** removed the smoke test "access logs arrive;
  saved Athena queries run", the test "WAF blocks appear as 403 in the logs",
  the matching open-question item (in the criteria and in the checklist's
  section B), the housekeeping items for the saved Logs Insights queries and
  the access-log table's year range, and the privacy-notice note about access
  logs holding IP addresses (it now says those logs are gone and the function
  log holds no personal data). Tests after the removed one were renumbered
  (closed poll is 13, main site 14) and the reference to it in section B
  followed.
- **Added:** smoke test 12, `make -s check-polls` against production returning
  one summary (test submissions as log lines, daily metrics present,
  `incomplete_metrics` empty), marked **Open** because it needs the redeploy
  that sets the log group's fixed name. The same test is in the build plan's
  first-deploy step.
- **Build plan:** a status note at the top; the resource list no longer
  includes logging, Glue, Athena or saved queries; step 6c is marked
  superseded; the stack-test assertion about the logs bucket is gone; the
  "CloudFront logs appear" check in the first-deploy smoke tests is replaced by
  the `check-polls` one; the "logging lag" risk is removed; the definition of
  done no longer asks for the observability inference (it says why). The
  build plan's finished P0 spike record still lists the log-delivery, Glue and
  Athena constructs as having existed; that is history, and a parenthetical
  now says they were later removed.
- **Issues 12 and 13 (earlier effort):** each carries a "Superseded" line under
  its header and a dated comment. I left their `Status:` lines and checked
  criteria alone, since they record what was true when built. One side effect to
  know about: issue 13 still reads `Status: ready-for-agent` although it is
  finished and superseded, so a tool that scans for ready-for-agent issues
  could pick it up. Say if you want it set to `wontfix`.
- **`issues.json`** (the export that duplicates the issue bodies) was kept
  consistent: superseded notes on entries 12 and 13, and the same criterion
  edit on entry 15. It round-trips byte for byte, so the diff is only those
  lines.
- **Left unchanged on purpose:** every other launch criterion and check
  (rows 1 to 11 and 14, the open questions about free text, throttling and the
  closed poll, the privacy and poll decisions, the remaining housekeeping). The
  earlier effort's spec and map still describe the access logs; the prune slice
  adds the "Changes since this spec" note.
- Documentation only: no code or tests changed, so I did not re-run the gate.
