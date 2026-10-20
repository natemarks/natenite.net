# Build plan: polls.natenite.net

Derived from the closed wayfinder map (`map.md`) and its tickets. Every design choice below is a decision already made there; this document orders the work and says how to know each piece is done. Items marked **VERIFY** were not confirmed in the research and must be checked when the step is reached. Nothing here has been built.

**Status, 2026-10-20:** the build is done and this plan is kept only until the planning docs are pruned. The simplify-polls effort removed the CloudFront access logs and everything built on them (the logs bucket, log delivery, the Glue table, the Athena workgroup and queries, and the saved Logs Insights queries); step P6c is marked superseded and the checks for those pieces are gone. Other parts of this plan describe the original design and are left as written.

## What gets built

| Piece | Where | Decided in |
|---|---|---|
| Shared poll page (`index.html`, `app.js`, `lib.js`, stylesheet) | `site/polls/` | architecture decision 6, layout decision 8 |
| Poll definitions, one JSON per poll | `polls/` | poll definition ticket (5, 6, 10) |
| Submit handler (Python), limits, validation, event logging | `lambda/submit/` (with symlink `polls` -> `../../polls`) | architecture 5, 7; abuse limits; layout 3 |
| Settings | `config/production/polls/polls.json`, `PollsSetting` in `config/settings.py` | layout 7 |
| Stack | `stack/polls.py`: `PollsInput`, `PollsStack` (`NateNiteProductionPollsStack`) | layout 2, 6 |
| Shared WAF ACL change | `stack/site.py`: rate rule (and ACL stays exported) | architecture 3; abuse limits 1 |
| Wiring | `config/inventory.py` | layout 1 |
| Tests | `tests/unit/...`, `site/polls/*.test.js`, golden data under `test_data/` | layout 4, 5, 8 |
| Make targets, CI | `Makefile`, `.github/workflows/static-checks.yml` | layout 6, 8 |

Resources `PollsStack` creates (all in `us-east-1`): S3 site bucket (private, OAC); `BucketDeployment` for the page and definitions; Python Lambda (reserved concurrency 2) with a Function URL (`AWS_IAM`) and a log group (365-day retention); DynamoDB on-demand table (retained, deletion protection, PITR off); CloudFront distribution for `polls.natenite.net` (cert reused from `CertificateStack`, existing web ACL attached, S3 origin plus Lambda origin on `/submit`, viewer-request rewrite function); Route 53 alias record.

Expected running cost: about $1 a month for the rate rule, plus cents (Lambda, DynamoDB, CloudFront, S3, CloudWatch). Prices: `research/06-verified-pricing.md`.

## Ordering and dependencies

```
P0 spikes ─┬─> P1 settings ──┐
           ├─> P2 handler ───┤
           ├─> P3 polls/*.json ┤
           ├─> P4 page + JS ──┼─> P6 PollsStack ─> P7 golden tests ─> P9 deploy ─> P10 launch
           └─> P5 SiteStack ──┘          ^
                                         └ P8 make/CI/docs can run alongside P6
```

P2, P3 and P4 need no AWS and can be done in any order or in parallel. P6 needs P1 to P5. Sizes: S (under half a day), M (about a day), L (a few days).

## P0. Spikes (S): confirm the open items locally, before building on them

All local synth or docs checks; no AWS resources. Record answers in the PR or a note.

1. **Done (issue 01):** in the pinned `aws-cdk-lib` (now 2.273.0), these were confirmed to exist: `cloudfront_origins.FunctionUrlOrigin.with_origin_access_control`; `lambda_.Code.from_asset(..., follow_symlinks=...)` with `SymlinkFollowMode.ALWAYS`; `aws_logs.CfnDeliverySource`, `CfnDeliveryDestination`, `CfnDelivery` and the property that selects JSON output; `aws_glue.CfnTable`, `aws_athena.CfnWorkGroup`, `CfnNamedQuery`; `aws_logs.CfnQueryDefinition`; the Lambda runtime constant you will use (the log-delivery, Glue, Athena and saved-query constructs were later removed along with the access-log layer). In 2.260.0 the Function URL OAC origin added only one of the two required Lambda permissions; 2.273.0 adds both, so the repo was bumped to 2.273.0 as its own change before building.
2. Confirm asset hashes appear in the synthesized template for a Lambda `Code.from_asset` and a `BucketDeployment` (drives the helper in P7).
3. Confirm `node` is available to `make unit-test` locally and note the version for CI.

Done when: each item is answered yes/no with the exact API names, and any "no" has a workaround noted.

## P1. Settings (S)

- Add `PollsSetting(JsonSettingBase)` to `config/settings.py` with `RELATIVE_PATH_TEMPLATE = "polls/polls.json"` and fields: `subdomain` (`"polls"`), `reserved_concurrency` (2), `rate_limit` (20), `rate_window_seconds` (300).
- Add `config/production/polls/polls.json` with those values.
- Extend `tests/unit/config/settings/` following the existing `test_settings.py` pattern (golden or case data under `test_data/unit/config/settings/...`).

Done when: `make unit-test` passes and the settings load from `config/production`.

## P2. Submit handler (M)

Files under `lambda/submit/`:

- `limits.py`: constants (free text 500 characters, email 254, body 6 KB). Imported by the handler and by the poll-validation test.
- `validate.py`: pure functions: parse body, enforce size, check poll exists and `closesAt` (UTC) has not passed, validate each answer against its question (single choice = one option ID; multiple choice = list of option IDs; rating = integer within min/max; free text = string within the cap), optional email format and length.
- `handler.py`: Function URL entry point. Loads definitions from the `polls/` folder next to it; builds a time-sortable response ID (ULID-style, standard library only); writes `RESPONSE#<id>` (answers by question ID, hashed browser token, submitted-at, poll definition version) and, when an email is present, `EMAIL#<id>` to the table through an injected table function; returns clear JSON errors (400, 404 unknown poll, 410 or 403 closed poll, 413 oversize). Emits one structured JSON log line per request outcome. Never logs the email or any answer text.
- Table keys: partition key = `POLL#<pollId>`, sort key = `RESPONSE#<ulid>` or `EMAIL#<ulid>`. Assumption to confirm while building: each poll JSON carries an integer `version` that is stored on the response.
- Tests in `tests/unit/lambda_submit/` using an in-memory fake table (no new dependency): each question type valid and invalid, closed poll, oversize body, missing poll, email stored as a separate record, no personal data in log lines, response IDs sort by time.

Done when: tests cover every rule above and `make static` passes (black at 79 columns, pylint).

## P3. Poll definitions and their validation (S)

- Define the JSON shape: `id`, `title`, `version`, optional `closesAt`, `questions[]` with `id`, `type` (`single`, `multi`, `rating`, `text`), `prompt`, and options, rating bounds or length cap as relevant.
- Add `polls/poll1.json` as a working example (placeholder questions; authoring real questions is out of scope).
- Add `lambda/submit/polls` as a git symlink to `../../polls`.
- Add a unit test that loads every file in `polls/` and checks: valid types, unique IDs, valid `closesAt`, rating bounds, and that the worst-case request body (up to 4 bytes per character for every free-text cap, plus email and overhead) stays under the 6 KB limit.

Done when: a deliberately bad poll file fails the test, and the test runs in `make unit-test`.

## P4. Page and JavaScript (M)

- `site/polls/index.html`, `app.js`, stylesheet.
- `site/polls/lib.js`: pure logic with no DOM access: SHA-256 of the body for the `x-amz-content-sha256` header (via `crypto.subtle`), request body builder, retry/backoff timing.
- Behaviour: read the poll ID from the URL path; fetch `/definitions/<id>.json`; treat any non-200 as "poll not found" (S3 behind OAC typically returns 403 for a missing object when the caller lacks list permission; **VERIFY** on the deployed stack); render the form; remember a prior submission in `localStorage` and say so; generate a random browser token on first visit and send it; POST to `/submit` with the hash header; retry 429 and 5xx two or three times with backoff, then show the "busy, try again" message with the form still filled in; show a thank-you on success; one-line privacy notice near the email field.
- `site/polls/lib.test.js` run with `node --test`.

Done when: `node --test site/polls/` passes, the hash test uses a known SHA-256 vector, and the page works against a stub endpoint locally.

## P5. Shared ACL: rate rule (S to M)

- In `stack/site.py` add a rate-based rule to the existing `CfnWebACL`: limit 20 per 300 s per IP, action Block, scope-down matching Host = `polls.<default_fqdn>` AND URI path = `/submit` AND method = POST, visibility metrics on. `SiteInput` needs the polls subdomain, so load `PollsSetting` there (or pass the host in).
- Keep `self.web_acl` exposed so `PollsStack` can attach it.
- Update the Site golden file with `make unit-update_golden`, then read the diff: it should show only the new rule.

Done when: the golden diff contains only the rate rule. **VERIFY** the exact scope-down statement shape (AND of three statements) in the CDK docs.

## P6. PollsStack (L)

Build in `stack/polls.py` following the `SiteStack` pattern (`PollsInput.from_config_directory`, prefix `NateNiteProductionPolls`). Work in four slices; `cdk synth` after each.

**6a. Storage and compute.** DynamoDB table (on-demand, `RemovalPolicy.RETAIN`, deletion protection, PITR off). Lambda from `lambda/submit` with `follow_symlinks=ALWAYS`, reserved concurrency from settings, environment variable for the table name, least-privilege `dynamodb:PutItem` on the table, explicit log group with 365-day retention. Function URL with `AuthType: AWS_IAM`.

**6b. Distribution.** Private S3 site bucket with OAC. `BucketDeployment` for `site/polls/` at the root and `polls/*.json` under `definitions/`. CloudFront distribution: alias `polls.<fqdn>`, certificate from `CertificateStack`, existing web ACL from `SiteStack`, default behavior to S3 with a viewer-request rewrite function (extension-less paths except `/submit` map to `/index.html`), and an additional behavior for `/submit` to the Function URL origin with OAC (`FunctionUrlOrigin.with_origin_access_control`), all methods allowed, caching disabled, origin request policy that does not forward the viewer Host header (**VERIFY**). Route 53 alias record in the existing zone. Mind the existing `SiteStack` habit of index-based OAC overrides: do not copy it; with two origins use the L2 origins.

**6c. Logging and Athena. Superseded:** removed by the simplify-polls effort. The stack keeps the function's log group (a fixed name, 365-day retention) and nothing else for logs; problems are checked with `make -s check-polls`.

**6d. Wiring.** In `config/inventory.py` add `polls_stack(...)` and call it from `deploy_stacks` after `site_stack`, passing both the certificate and site stacks.

Done when: `cdk synth -c app_env=production` succeeds and `cdk ls` shows `NateNiteProductionPollsStack`.

## P7. Tests for the stack (M)

- Add a helper in `tests/helper.py` that replaces asset hashes (keys and metadata) with a placeholder before comparing, so golden files change only for infrastructure changes.
- Add `tests/unit/stack/test_polls.py`: one parametrized `production` golden test, constructing the certificate, site and polls stacks as `test_site.py` does. Generate with `make unit-update_golden`, then read the file.
- Add targeted assertions that matter beyond the golden: reserved concurrency is 2, the function URL is `AWS_IAM`, the table is retained with deletion protection, the log group retention is 365 days.
- Add `node --test` to `make unit-test`.

Done when: `make static` passes with no skipped checks.

## P8. Make targets, CI, docs (S)

- `Makefile`: `deploy-polls` (runs unit tests, then CDK deploy of `NateNiteProductionPollsStack`) and `diff-polls`.
- `.github/workflows/static-checks.yml`: add a pinned `actions/setup-node` step so `make static-check` can run `node --test`.
- Docs: add a short section to `README.md` (how to add a poll: edit `polls/`, `make static`, `make diff-polls`, `make deploy-polls`); note the new stack in `AGENTS.md`/`CLAUDE.md` if they list stacks. `CONTEXT.md` and ADR 0001 already exist.

## P9. First deploy and verification (M)

Prerequisites: CDK bootstrapped for the account and region (`make cdk-bootstrap`), AWS credentials for account `605560722292` (profile `mp-mgmt`).

1. `make static`, then `make diff-polls`; read the diff. Note: deploying the polls stack also updates `SiteStack` (the new rate rule) because of the dependency, which touches the live main-site ACL; check the Site diff in isolation first.
2. `make deploy-polls`.
3. Smoke tests, recording results:
   - Page loads at `https://polls.natenite.net/poll1`; unknown ID shows "poll not found".
   - A real submission through the page succeeds; a `RESPONSE#` (and `EMAIL#` when given) record appears in the table; email is not present in the Lambda logs.
   - A request straight to the raw `*.lambda-url` address is rejected (IAM).
   - A POST without the `x-amz-content-sha256` header fails, with it succeeds.
   - Oversize body (over 6 KB) gets the Lambda's clear error; over 8 KB is blocked by WAF (**VERIFY** the behaviour and status).
   - Free text containing HTML-like characters is not blocked by the managed rules (**VERIFY**; if it is, decide whether to override a rule to Count).
   - Rate rule: more than 20 POSTs to `/submit` in 5 minutes from one IP gets blocked.
   - Throttling: drive concurrency above the cap and confirm HTTP 429, then check which of `Url4xxCount`, `Throttles` and `ConcurrentExecutions` moved (closes the open inference in the abuse limits ticket).
   - `make -s check-polls` runs against production and returns a summary: the test submissions appear as log lines, the daily metrics are present, and `incomplete_metrics` is empty. (The log group has a fixed name, so this needs the deploy that sets it.)
4. Confirm the main site is unaffected (apex and `www` still load).

Rollback: `cdk destroy NateNiteProductionPollsStack` removes everything except the retained table and (if you chose retention) any logs you keep; the Site rate rule remains until reverted in `site.py` and redeployed.

## P10. Launch checklist (not architecture)

- Privacy notice wording on the form, and a decision on whether any privacy regime applies to collecting an email (legal basis was never researched).
- Real poll questions in `polls/` (authoring is out of scope of this plan).
- Decide whether to keep the example `poll1.json` live.

## Risks and watch-points

- **OAC with POST:** the body-hash header is mandatory through the Function URL path; a mismatch looks like a 403 from CloudFront or Lambda. The `lib.js` test with a known vector is the guard.
- **Shared ACL coupling:** the polls stack imports the Site stack's ACL; with strong cross-stack references the export becomes hard to remove or rename later. Treat the ACL ARN export as permanent, or move the ACL to its own stack if that bothers you.
- **Managed rules on free text:** the Core rule set may block some free-text content (only 5 of 22 rules were read). Smoke-test it.
- **Concurrency cap of 2:** a burst above 20 requests per second loses submissions until retry; adjustable in `polls.json`.
- **Version drift:** `requirements.txt` pins `aws-cdk-lib==2.273.0` (bumped from 2.260.0 after the spike; all existing golden tests pass unchanged). Library bumps change the library-provided asset hashes in templates, so keep the golden-test helper normalizing every asset hash.
- **Golden tag side effect:** do not fix the `iac_project_url` typo (`natenate.net`) inside this work; it is the `iac` tag on every resource and changing it rewrites every golden file. Do it as a separate change.

## Definition of done

`make static` passes; the stack deploys from a clean checkout; every smoke test above has a recorded result; the open inference from the abuse limits ticket is answered (the observability one, WAF blocks in the CloudFront logs, is moot now that the access logs are gone); the launch checklist items are either done or consciously deferred.
