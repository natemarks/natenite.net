Status: ready-for-agent
Type: AFK
Blocked by: 03

# 11. Handler event logging, 365-day retention and saved Logs Insights queries

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The function writes one structured JSON log line per request outcome (accepted, rejected with a reason, error) with no email or answer text. Its log group retains entries for 365 days, and the stack defines saved Logs Insights queries for the routine check. No alarms or notifications.

## Acceptance criteria

- [x] Entry-point tests assert one structured log line per outcome and that no email address or answer text appears in any line.
- [x] Template assertions: the log group retains 365 days; saved Logs Insights queries exist; no alarm or notification topic exists.
- [x] The golden file is updated and read.
- [x] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 52, 53, 54, 55, 56

## Comments

- 2026-10-17: claimed; seams are the handler entry point (log lines captured from stdout) and the stack template. Confirming design choices with the owner before writing tests.

### Progress (2026-10-17): code complete; verification after deploy needs the owner

Built test-first at the confirmed seams (the handler entry point, reading log lines from standard output as Lambda captures them, and the stack template). Gate: pylint 10.00, 260 Python tests, 41 Node tests. Only the polls golden file changed.

**The log line** (`print` of one JSON object; Python's `logging` is avoided because Lambda wraps its messages in a text prefix that would hide the JSON): `level`, `event` ('submission'), `outcome`, `status`, `reason` (rejections and errors), `pollId`, `responseId`, `hasEmail`, `hasBrowserToken`, `bodyBytes`, `at`, `requestId`, `cloudfrontRequestId` (from the `x-amz-cf-id` header, so a handler line can be matched to its CloudFront access-log line), plus `errorType` and `errorCode` on unexpected failures. Levels: INFO accepted, WARN any rejection (4xx), ERROR any 5xx. Exactly one line per request, whatever the outcome (tested across accepted, bad answers, bad JSON, unknown and hostile poll IDs, closed polls, wrong method and path, oversize, a lost email, and an unexpected failure).

**Never logged:** answers, the email, the browser token or its hash, the raw body, IP addresses. `pollId` appears only when it names a real poll, otherwise null, so attacker-controlled text cannot enter the logs (a test sends a poll ID containing a newline and a fake log line, and gets one honest line). A content guard sends distinctive secrets through a mix of accepted, rejected, lost-email and failed requests and asserts none appears in the output; it was proven able to fail by temporarily logging the raw body, which failed it; the handler was restored.

**Unexpected failures:** anything escaping from the table now returns a clean `500 internal_error` (the page already retries 5xx) instead of a Lambda error, and logs an ERROR line with only the error type and AWS error code, never the message (a test puts a distinctive string in the message and asserts it is absent from the log and the response).

**Stack:** an explicit log group with 365-day retention and `DeletionPolicy: Retain` (the lines hold no personal data and are the audit trail), attached to the function through its logging configuration; four saved Logs Insights queries in a `polls/` folder (`rejections-by-reason`, `errors`, `submissions-per-day`, `recent-requests`), each searching that group; tests assert there are no alarms and no notification topics. The golden diff adds exactly one log group and four query definitions and changes only the function (its `LoggingConfig`).

**Tidy-ups noted:** `handle` passes its logging context in one `facts` dictionary and its collaborators together to stay inside the argument limit; the handler test module passed 1,000 lines and carries a `too-many-lines` pragma (it is one flat list of independent tests, so a split would be mostly churn; the handler slices are nearly done).

**Deployment side effect:** the function currently writes to a log group Lambda created itself (`/aws/lambda/<function name>`), which never expires and is not managed by CloudFormation. After this deploy new lines go to the new group and the old group stays behind with its old `START`/`END`/`REPORT` lines (no personal data). Delete it by hand whenever convenient.

Not done:
- [x] After `make deploy-polls`, check it live: (1) find the new group and its retention: `aws logs describe-log-groups --query "logGroups[?contains(logGroupName,'SubmitLogGroup')].{name:logGroupName,retention:retentionInDays}"` should show 365; (2) submit once on `https://polls.natenite.net/poll1` and once with a deliberately bad request (for example the signed `curl` with an unknown option); (3) `aws logs tail <that group name> --since 10m` should show one JSON line per request (INFO accepted, WARN rejected) with no answer text; (4) in the console, CloudWatch > Logs Insights > Queries > Saved queries > `polls`, run `recent-requests` and `rejections-by-reason`; (5) find the old group with `aws logs describe-log-groups --log-group-name-prefix /aws/lambda/NateNiteProductionPollsStack --query 'logGroups[].[logGroupName,retentionInDays,storedBytes]' --output table` (the one with no retention) and delete it with `aws logs delete-log-group --log-group-name <that name>`. Then delete your test records as before.

### Deployed (2026-10-17 UTC)

The owner deployed slice 11. Verified from the delete script's checks (run against the real account): the function now logs to the new managed group, `NateNiteProductionPollsStack-NateNiteProductionPollsSubmitLogGroup5C4BB9CB-…`, which keeps logs for 365 days; the old Lambda-created group (never expires, 1,301 bytes, created 2026-10-16 12:52 UTC) received its last event 31 minutes before the check, which also shows the function really stopped writing there. A throw-away script (kept outside the repo, with safety checks and a dry-run default) is the way the old group gets deleted; its first version failed safely (a stray `None` printed by the AWS CLI's `--max-items` was read by bash as a variable), nothing was deleted, and it was fixed to use `--limit 1` and parse defensively.

Still to do by hand, if not done yet: delete the old log group with that script (`--yes`), and the live JSON-line and saved-query checks listed above (the JSON lines were not yet inspected in the real log group in this session).
