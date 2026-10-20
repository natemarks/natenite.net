# Polls

Simple public polls at `https://polls.natenite.net/<poll-id>`. A visitor
answers a poll's questions and may leave an email address. Only the owner can
read the data. This page is the owner's guide: how to manage polls, read their
results, and watch for problems. `make help` lists every command.

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

Commands that talk to AWS need the login and the `AWS_PROFILE` export. The
account is NateNite Production, region `us-east-1`; commands default to
`app_env=production`. The problem check and counting recipes also need `jq`.

## Managing polls

### Add a poll

1. **Write the definition** as `polls/<poll-id>.json`. The file name must
   match the `id`. `docs/examples/all-question-types.json` shows every question
   type (it is not published; only `polls/` is).
2. **Run the unit tests:** `make unit-test`. They check the structure of every
   file in `polls/`, so a mistake (a duplicate option, a rating range that is
   too wide, a bad closing time) fails here, before anything is deployed, with
   a message that names the file and the rule.
3. **Preview:** `make diff-polls` shows what a deploy would change.
4. **Deploy:** `make deploy-polls`. It runs the unit tests first, then
   deploys the polls stack and anything it depends on. The page deployment
   also clears CloudFront's cache.
5. **Check the live page:** open `https://polls.natenite.net/<poll-id>` and
   submit a test answer. That response is real data (see
   [Remove a response](#remove-a-response)). If the submission fails, run
   `make -s check-polls`: a `payload_too_large` rejection means the poll is too
   big to submit, so shorten it. Nothing checks this before the deploy.

### Definition format

A poll is one JSON file with an `id` (the address: lower-case letters, digits
and hyphens), a `title`, a whole-number `version`, an optional `closesAt` (UTC,
like `2026-12-31T23:59:59Z`) and a list of `questions`. Each question has an
`id`, a `prompt` and a `type`: `single` or `multi` (with `options`, each an
`id` and a `label`), `rating` (a whole number from `min` to `max`) or `text`.
Every poll also offers an optional email field. Size limits are in
`lambda/submit/limits.py`; the unit tests' messages state every other rule.
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

### Remove a response

There is no make target. Delete the one item by key (take the `pk` and `sk`
from the file `make dump-poll` writes, and double check them):

```console
aws dynamodb delete-item --region us-east-1 \
  --table-name natenite-production-polls-responses \
  --key '{"pk":{"S":"POLL#<poll-id>"},"sk":{"S":"RESPONSE#<id>"}}'
```

### Check everything before a deploy

`make static` formats, lints and tests (use it while working); `make
static-check` is the read-only gate the CI runs. Run `make unit-update_golden`
only when an infrastructure change is intentional, and read the diff first.

### Roll back

`cdk destroy NateNiteProductionPollsStack` removes the polls stack. The
responses table and the log group are kept. The rate-limit rule lives in the
Site stack and stays until it is removed in `stack/site.py` and redeployed.

## Reading results

### Responses

```console
make dump-poll poll=<poll-id>            # answers, and whether each visitor left an email
make dump-poll poll=<poll-id> emails=1   # ...and the email addresses too
```

Either writes `.polls-results/<poll-id>.json` (git-ignored, readable by you only,
replaced on each run) and prints only a one-line summary. The file is a JSON
array, one object per response, in submission order, with sorted keys (so the
same data gives the same text):

```json
{
  "answers": {"dates": ["sat-nov-7", "sun-nov-8"]},
  "browserTokenHash": "9f2c...",
  "email": "reader@example.com",
  "hasEmail": true,
  "pk": "POLL#nov20267s-in-603",
  "pollVersion": 1,
  "sk": "RESPONSE#20261016T140322418302Z-9f2c1a7e44b0d3a1",
  "submittedAt": "2026-10-16T14:03:22Z"
}
```

- Answers are keyed by question `id`: an option `id` for `single`, a list of
  them for `multi`, a number for `rating`, the text for `text`.
- `sk` holds the response ID: the UTC time to the microsecond, then random
  hex, so responses sort by submission time. `pollVersion` is the definition
  version the visitor saw.
- `browserTokenHash` hashes a random token the visitor's browser keeps; it is
  how the page tells a visitor they already answered. Responses with the same
  hash came from one browser (repeats are not blocked, so decide how to count
  them); none means the browser sent no token.
- `hasEmail` says whether the visitor left an address. `email` (only with
  `emails=1`) is the address or `null`. With it the file ties each answer to a
  person: keep it out of shared places. If a response was deleted on its own,
  its email record is left behind; the command counts those on stderr (never
  printing an address) and `make delete-email` removes them.

Counting with `jq`, for a poll whose question `id` is `dates` (the recipes
need no addresses):

```console
F=.polls-results/<poll-id>.json

# votes per option, every response counted
jq '[.[].answers.dates[]] | group_by(.) | map({date: .[0], votes: length})' $F

# the same, counting each browser's latest response once
jq 'group_by(.browserTokenHash // .sk) | map(last)
    | [.[].answers.dates[]] | group_by(.) | map({date: .[0], votes: length})' $F

# how many responders left an email, and their share (a measure of engagement)
jq '(map(select(.hasEmail)) | length) as $n
    | {responders: length, left_an_email: $n, share: (if length > 0 then $n / length else null end)}' $F
```

For a `single` question use `.answers.<id>` without `[]`; for `rating`, group
the numbers the same way.

### Email addresses

Email addresses are separate records, linked to a response by the same ID.
`make dump-poll poll=<poll-id> emails=1` joins them into the results file; to
read the records themselves:

```console
aws dynamodb query --region us-east-1 \
  --table-name natenite-production-polls-responses \
  --key-condition-expression 'pk = :pk AND begins_with(sk, :p)' \
  --expression-attribute-values '{":pk":{"S":"POLL#<poll-id>"},":p":{"S":"EMAIL#"}}'
```

Each record has `email`, `submittedAt`, and an `sk` of `EMAIL#<id>` matching
the response's ID. The address is used only to coordinate and promote lacrosse
events, and is kept until its removal is requested (the form's notice says so).

Managing addresses (these only report what they would do until you add
`yes=1`, and list record keys and dates, never the addresses):

```console
make purge-emails days=365            # addresses older than a year
make purge-emails days=365 yes=1      # ...and delete them
make delete-email email=a@b.co        # records for one address (a removal request)
make delete-email email=a@b.co yes=1  # ...and delete them
```

Deleting an email record leaves the response itself in place.

## Checking for problems

Nothing is automatic: there are no alarms. Run the check weekly while a poll is
open, and daily around a launch.

```console
make -s check-polls            # the last 90 days
make -s check-polls days=7     # a shorter window
```

It downloads the function's log and a few daily metrics into `.polls-check/`
(git-ignored) and prints one JSON document. It only reads from AWS, and needs
the login above, `jq` and GNU `date`. Read it in this order:

1. **`logs.errors`**: every request that failed on our side, newest first,
   with its `timestamp`. **Look here first.** `errorType` and `errorCode` say
   what failed (for example a DynamoDB error).
2. **`logs.rejections_by_reason`**: why submissions were turned away, most
   frequent first. `logs.requests` and `logs.outcomes` give the totals.
3. **`metrics`**: one entry per series with its value for each UTC day that
   has data (a day that is missing had none, which for these counts means
   zero), the peak day (`max`, `max_day`), and for counts a `total`:
   - `shared firewall blocked requests, rule ...`: blocks by rule on the web
     ACL the main site shares, so they include its traffic.
   - `polls firewall blocked requests`: blocks on the polls site alone. A jump
     is worth a look: a rule may be turning away real visitors (the firewall
     console's sampled requests show what was blocked).
   - `function invocations`, `errors`, `throttles`: the submit function.
   - `distribution requests` and its 4xx and 5xx error percentages (the 4xx
     percentage includes the function's rejections).
4. **`incomplete_metrics`**: series CloudWatch did not return in full. Do not
   trust a quiet result for those.

`make fetch-logs` and `make fetch-metrics` refresh one half. The raw files stay
in `.polls-check/` to search with `jq`, for example:

```console
jq -c 'select(.reason == "unknown_option")' .polls-check/handler.jsonl
```

### What a log line holds

One JSON line per request: `level` (`INFO` accepted, `WARN` rejected, `ERROR`
failed), `outcome`, `status`, `reason` (when refused or failed), `pollId` (only
for a real poll), `responseId`, `bodyBytes`, `requestId`, and for failures
`errorType` and `errorCode`. It never holds answers, email addresses, tokens,
IP addresses or the raw body, so it is safe to share. The log group is
`/natenite/production/polls/submit`.

### What the reasons mean

| Reason | Status | Usually |
| --- | --- | --- |
| `poll_closed` | 410 | A visitor arrived after `closesAt`. Expected. |
| `unknown_poll` | 404 | A wrong address, or a poll that was unpublished. |
| `payload_too_large` | 413 | A poll too big to submit, or a hand-made request. `bodyBytes` shows by how much. |
| any other 400 | 400 | The visitor's data did not fit the definition. A few are normal. **A steady stream for one poll means the page and the definition disagree** (for example an edited poll that was not deployed). |
| `method_not_allowed`, `not_found` | 405, 404 | Someone probing `/submit`. Harmless. |
| `email_not_stored` | 500 | The answers were saved but the email address was not; the page tells the visitor to retry. Investigate. |
| `internal_error` | 500 | Something failed in the function. Read `errorType` and `errorCode` in `logs.errors`. |

Anything at `ERROR` level is a problem to follow up. Rows of `WARN` are mostly
visitors' mistakes.

## What is kept and what it costs

- The function's log is kept for a year. Responses stay until you remove them;
  email records until removal is requested.
- Expect about $1 a month for the firewall rule, plus cents for the rest.
- Limits live in code and settings: sizes in `lambda/submit/limits.py`, the
  submit rate limit in `config/production/polls/polls.json`, and why the
  function has no reserved concurrency in the note on `PollsSetting` in
  `config/settings.py`.
