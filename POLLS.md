# Polls

Simple public polls at `https://polls.natenite.net/<poll-id>`. A visitor
answers a poll's questions and may leave an email address. Only the owner can
read the data. This page is the owner's guide: how to manage polls, read their
results, and watch for problems.

Background and decisions:

- Terms: [CONTEXT.md](./CONTEXT.md) (poll, response, answer, email record).
- Why it is built this way:
  [ADR 0001](./docs/adr/0001-lambda-function-url-with-cloudfront-oac.md).
- Full requirements: the [spec](./.scratch/wayfinder/poll-app/spec.md).

## How it fits together

```
visitor ──> CloudFront (polls.natenite.net) ──> S3: the page and poll definitions
               │  (shared web ACL: managed rules + a rate limit on POSTs)
               └── POST /submit ──> Lambda (checks the answers) ──> DynamoDB
```

- Poll definitions are files in `polls/` in this repository. Publishing a poll
  means deploying.
- The Lambda checks every submission against the definition it was deployed
  with, and stores a response (and, if one was given, a separate email
  record). There is no public way to read anything back.
- The table is kept if the stack is deleted, and deletion protection is on.

## One-time setup

```console
make .venv
make node_modules
aws sso login --profile mp-mgmt
export AWS_PROFILE=mp-mgmt
```

Every command below that talks to AWS needs the login and the `AWS_PROFILE`
export (`make` runs them in this shell). The account is NateNite Production,
region `us-east-1`. The commands default to `app_env=production`.

## Managing polls

### Add a poll

1. **Write the definition** as `polls/<poll-id>.json`. The file name must
   match the `id`. `docs/examples/all-question-types.json` shows every question
   type (it is not published; only `polls/` is).
2. **Run the unit tests:** `make unit-test`. They check every file in
   `polls/`, so a mistake (a duplicate option, a rating range that is too
   wide, a poll too big to submit) fails here, before anything is deployed.
3. **Preview:** `make diff-polls`. Adding a poll should change only the poll
   files (the definitions upload and the function bundle).
4. **Deploy:** `make deploy-polls`. It runs the unit tests first, then
   deploys the polls stack and anything it depends on. The page deployment
   also clears CloudFront's cache.
5. **Check the live page:** open `https://polls.natenite.net/<poll-id>`.
   If you submit to test it, that response is real data (see
   [Remove a response](#remove-a-response)).

### Definition format

```json
{
  "id": "poll-id",
  "title": "Shown at the top of the page",
  "version": 1,
  "closesAt": "2026-12-31T23:59:59Z",
  "questions": [ ... ]
}
```

| Field | Rule |
| --- | --- |
| `id` | Lower-case letters, digits and hyphens; equals the file name. It is the address: `polls.natenite.net/<id>`. |
| `title` | Non-empty text. |
| `version` | Whole number, at least 1. Each stored response records the version it answered. |
| `closesAt` | Optional, UTC, exactly as above. After it the page says the poll is closed and the function refuses submissions (HTTP 410). |
| `questions` | A non-empty list. Each has a `prompt`, a `type`, and an `id` that starts with a lower-case letter and uses letters, digits and underscores. |

Question types:

| `type` | Extra fields | Stored answer |
| --- | --- | --- |
| `single` | `options`: at least two, each with an `id` and a `label` | one option `id` |
| `multi` | `options`, as above | a list of option `id`s |
| `rating` | whole-number `min` and `max`, at most 10 steps apart | a whole number in range |
| `text` | none | the text, up to 500 characters |

The email field appears on every poll and is optional. A submission body may
not exceed 6 KB, so a poll can hold at most two free-text questions; the unit
tests check this for you.

A working example is `polls/nov20267s-in-603.json`.

### Change a poll that is open

Edit the file, **raise `version`**, and deploy as above. Do not change what an
existing option `id` means: old responses keep their old `id`s and are read
against the new definition.

### Close, unpublish or remove a poll

- **Close:** add `closesAt` and deploy. Responses already stored are kept.
- **Unpublish:** delete the file and deploy. Visitors can no longer load the
  poll and the function refuses submissions (`unknown_poll`, 404). **The
  stored responses stay in the table**; read them first if you still need
  them.
- **Remove a response:** there is no make target. Delete the one item by key
  (take the `pk` and `sk` from `make dump-poll`, and double check them):

  ```console
  aws dynamodb delete-item --region us-east-1 \
    --table-name natenite-production-polls-responses \
    --key '{"pk":{"S":"POLL#<poll-id>"},"sk":{"S":"RESPONSE#<id>"}}'
  ```

### Check everything before a deploy

- `make static`: formatters, linters and all unit tests (use while working).
- `make static-check`: the read-only gate the CI runs.
- `make unit-update_golden`: only when an infrastructure change is
  intentional; read the golden-file diff before accepting it.
- `make cdk-ls`, `make cdk-diff-all`: the same checks for every stack.

### Roll back

`cdk destroy NateNiteProductionPollsStack` removes the polls stack. The
responses table and the log groups are kept. The rate-limit rule lives in the
Site stack and stays until it is removed in `stack/site.py` and redeployed.

## Reading results

### Responses

```console
make -s dump-poll poll=<poll-id> > responses.json
```

The output is a JSON array, one object per response, in submission order, with
sorted keys (so the same data gives the same text):

```json
{
  "answers": {"dates": ["sat-nov-7", "sun-nov-8"]},
  "browserTokenHash": "9f2c...",
  "pk": "POLL#nov20267s-in-603",
  "pollVersion": 1,
  "sk": "RESPONSE#01K...",
  "submittedAt": "2026-10-20T14:03:22Z"
}
```

- Answers are keyed by question `id`, in the shapes in the table above.
- `sk` is a time-sortable response ID. `pollVersion` is the definition version
  the visitor saw.
- `browserTokenHash` is a hash of a random token the visitor's browser keeps.
  It is how the page tells a visitor they already answered. Two responses
  with the same hash came from the same browser; the table does not block a
  repeat, so decide how to count them. Responses with no hash came from a
  browser that did not send a token.
- Email addresses are not in this output.

Counting with `jq` (if installed), for a poll whose question `id` is `dates`:

```console
# votes per option, every response counted
jq '[.[].answers.dates[]] | group_by(.) | map({date: .[0], votes: length})' responses.json

# the same, counting each browser's latest response once
jq 'group_by(.browserTokenHash // .sk) | map(last)
    | [.[].answers.dates[]] | group_by(.) | map({date: .[0], votes: length})' responses.json
```

For a `single` question use `.answers.<id>` without `[]`; for `rating`, group
the numbers the same way.

### Email addresses

Email addresses are stored as separate records, linked to a response by the
same ID, and are never printed by the scripts. To read them:

```console
aws dynamodb query --region us-east-1 \
  --table-name natenite-production-polls-responses \
  --key-condition-expression 'pk = :pk AND begins_with(sk, :p)' \
  --expression-attribute-values '{":pk":{"S":"POLL#<poll-id>"},":p":{"S":"EMAIL#"}}'
```

Each record has `email`, `submittedAt`, and an `sk` of `EMAIL#<id>` where
`<id>` matches the response's ID. The address is used only to coordinate and
promote lacrosse events, and is kept until its removal is requested (the
notice on the form says so).

Managing addresses (both commands only report what they would do until you add
`yes=1`; they list record keys and dates, never the addresses):

```console
make purge-emails days=365            # addresses older than a year
make purge-emails days=365 yes=1      # ...and delete them
make delete-email email=a@b.co        # records for one address (a removal request)
make delete-email email=a@b.co yes=1  # ...and delete them
```

Deleting an email record leaves the response itself in place.

## Monitoring for problems

Nothing here is automatic. There are no alarms or notifications; the design
chose a periodic check by the owner. A good routine is to run both checks
below once a week while a poll is open, and once a day around a launch.

### 1. CloudFront access logs (what visitors and the firewall did)

```console
make -s query-logs > logs.json        # the last 90 days
make -s query-logs days=7 > logs.json # a shorter window
```

The output is one JSON document with `days`, `from`, `to` and a `queries` map,
each query a list of rows (every value is text):

| Query | What it answers |
| --- | --- |
| `polls/errors-by-day` | Requests with a status of 400 or more, by day, status and result type. |
| `polls/top-client-addresses` | The 20 busiest addresses, with how many requests were blocked (403) or rejected (4xx or 5xx). |
| `polls/blocked-and-throttled` | The latest 100 requests that returned 403 or 429. |

How to read them:

- **403 on `POST /submit`** is the firewall's rate limit (20 posts per 5
  minutes per address, an estimate rather than an exact count) or its managed
  rules. A few from one address is normal; many from many addresses is
  worth a look.
- **429** means the function was throttled. This shows up only in the access
  logs, never in the function's own log.
- **400** is the function refusing an answer (see the reasons below).
- The result type reads `Error` for all of these, so tell them apart by status.
- The command fails (exit 1, reason on stderr) if a query fails or takes
  longer than two minutes, and prints no partial report. An empty list is a
  real answer: nothing matched.
- The report includes client IP addresses from your own logs. Do not paste it
  anywhere public.
- The same three queries are saved in the Athena workgroup
  `NateNiteProductionPolls-access-logs` (database
  `nateniteproductionpolls_access_logs`, table `cloudfront_logs`) for the
  console, for the last 7 or 30 days.

### 2. The function's log (what the function decided)

The Lambda writes one JSON line per request and keeps them 365 days. Four
queries are saved in CloudWatch Logs Insights: in the AWS console go to
CloudWatch, Logs Insights, **Queries**, and pick one of these (they are
already pointed at the right log group; choose a time range):

| Saved query | What it answers |
| --- | --- |
| `polls/errors` | Requests that failed on our side (level `ERROR`): status, reason, `errorType`, `errorCode`, poll, response ID, request ID. **Look here first.** |
| `polls/rejections-by-reason` | Why submissions were turned away, counted. |
| `polls/submissions-per-day` | Accepted submissions per poll per day. |
| `polls/recent-requests` | The last 100 requests, one line each. |

A line holds the level (`INFO` accepted, `WARN` rejected, `ERROR` failed),
`status`, `reason`, `pollId` (only for a real poll), `responseId`,
`hasEmail`, `hasBrowserToken`, `bodyBytes`, `requestId` and
`cloudfrontRequestId`. It never holds answers, email addresses, tokens,
IP addresses or the raw body, so it is safe to share.

What the reasons mean:

| Reason | Status | Usually |
| --- | --- | --- |
| `poll_closed` | 410 | A visitor arrived after `closesAt`. Expected. |
| `unknown_poll` | 404 | A wrong address, or a poll that was unpublished. |
| `payload_too_large` | 413 | Body over 6 KB: a poll too big, or a hand-made request. |
| `invalid_json`, `invalid_request`, `unknown_question`, `missing_answer`, `unknown_option`, `duplicate_option`, `rating_out_of_range`, `invalid_answer`, `answer_too_long`, `invalid_email`, `email_too_long`, `invalid_token` | 400 | The visitor's data did not fit the definition. A few are normal. **A steady stream for one poll means the page and the definition disagree** (for example an edited poll that was not deployed). |
| `method_not_allowed`, `not_found` | 405, 404 | Someone probing `/submit`. Harmless. |
| `email_not_stored` | 500 | The answers were saved but the email address was not; the page tells the visitor to retry. Investigate. |
| `internal_error` | 500 | Something failed in the function. Find the line with `polls/errors` and read `errorType` and `errorCode` (for example a DynamoDB error). |

Anything at `ERROR` level is a problem to follow up. Rows of `WARN` are mostly
visitors' mistakes.

### Cost and limits to keep in mind

- A visitor's body is capped at 6 KB; free text at 500 characters.
- The firewall allows about 20 submissions per address per 5 minutes.
- The account's Lambda concurrency quota is 10, which is too low to reserve
  any for the polls function. Raising it lets you set
  `"reserved_concurrency": 2` in `config/production/polls/polls.json`.
- Retention: function logs and access logs 365 days; Athena query results 30
  days; responses stay until you remove them; email records until removal is
  requested.
- Expect about $1 a month for the firewall rule, plus cents for everything else.

## Command reference

| Command | What it does |
| --- | --- |
| `make unit-test` | Unit tests and poll-definition checks (no AWS). |
| `make static` / `make static-check` | Formatters, linters and tests; the second is the read-only CI gate. |
| `make diff-polls` | Preview what a deploy would change. |
| `make deploy-polls` | Run the tests, then deploy the polls stack. |
| `make -s dump-poll poll=<id>` | A poll's responses as JSON. |
| `make -s query-logs [days=N]` | The routine access-log queries as JSON (default 90 days). |
| `make purge-emails days=N [yes=1]` | Report or delete email addresses older than N days. |
| `make delete-email email=<address> [yes=1]` | Report or delete one address's records. |
| `make cdk-ls`, `make cdk-diff-all` | List stacks; diff every stack. |
