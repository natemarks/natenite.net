Status: ready-for-human
Type: HITL
Blocked by: 01

# 02. A poll page is live at polls.natenite.net/poll1

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Thin end-to-end path for a visitor to open a poll and see its form. Adds `PollsSetting` and its per-environment JSON, a first `PollsStack` (private S3 bucket with OAC, deployment of the shared page and the poll definitions, a CloudFront distribution at the polls hostname reusing the existing certificate and attaching the existing web ACL, the viewer-request rewrite function, and the Route 53 alias), inventory wiring after the Site stack, the make targets that preview and deploy the polls stack, and the golden-test helper that ignores asset hashes. The page renders a poll's title and single-choice questions from its definition; submitting comes in slice 03.

Human gate: the first production deploy, and checking the page in a browser.

## Acceptance criteria

- [x] A typed `PollsSetting` loads from `config/production`, with unit tests following the existing settings tests.
- [x] `PollsStack` is created from `PollsInput` for production and deploys after the Site stack; `cdk ls` shows `NateNiteProductionPollsStack`.
- [x] Referencing the Site stack's web ACL adds an export to the Site stack; the regenerated Site golden file differs only by that addition.
- [x] A golden test for the polls stack passes, and editing a poll definition or the page does not change the golden file (asset hashes are normalized by a shared test helper).
- [x] A make target previews the polls stack diff, and another runs the unit tests and then deploys it.
- [x] `make static` passes.
- [x] After deploy: `https://polls.natenite.net/poll1` shows the poll and its single-choice questions; an unknown poll ID shows a 'poll not found' message; the apex and `www` sites still load.
- [ ] The page works on a phone-sized viewport.

## Blocked by

- Blocked by 01

## User stories addressed

Spec user stories: 1, 2, 14, 20-25, 32, 33, 65-68, 70, 71

## Comments

- 2026-10-16: claimed; building up to the human gate (first production deploy). Progress notes appended below.

### Progress (2026-10-16): code complete up to the human gate

Built test-first at the seams confirmed with the owner (settings loading, stack template, asset-hash normalizer). `make static` passes: black unchanged, pylint 10.00, 22 unit tests (14 existing, 8 new).

What was added:
- `PollsSetting` (only `subdomain` for now; other fields arrive with the slices that use them) and `config/production/polls/polls.json`.
- `normalize_asset_hashes` in the test helpers, with literal before/after tests.
- `PollsInput` and `PollsStack` in `stack/polls.py`: private bucket (destroyed with the stack; content is rebuilt from the repo), distribution at the polls host (existing certificate, existing web ACL, HTTPS redirect, OAC origin, `index.html` root), a viewer-request function that serves the shared page for extension-less paths, an alias record in the existing zone, and two bucket deployments (page at the root excluding `definitions/*`; definitions under `definitions/`), each pruning only its own files and invalidating `/*`.
- Page files under `site/polls/` (`index.html`, `app.js`, `style.css`, all text set with `textContent`) and an example `polls/poll1.json` (placeholder questions).
- Inventory wiring after the Site stack, and `make diff-polls` / `make deploy-polls` (the latter runs the unit tests first; CDK's default approval prompt for IAM broadening stays on). Targets use the stack glob `*PollsStack` and were verified with `make -n`.
- Site golden regenerated: the diff is exactly the 13-line `Outputs` export of the web ACL ARN.

Findings:
- The existing golden pattern (`template.template_matches`) compares loosely: extra top-level sections such as `Outputs` do not fail it. The new polls golden test uses exact equality of the normalized template. The Site test now also builds the polls stack so its golden matches the deployed template. Consider moving the older golden tests to exact equality in a separate change.
- Edit stability confirmed: changing `polls/poll1.json` and `site/polls/style.css` left all 9 stack tests passing; both files restored afterwards.
- The page rendering and the rewrite function (inline JavaScript pinned by the golden file) are not covered by automated tests; they are checked at the deploy gate, as agreed.

Not done, needs the human (the gate):
- [ ] `cdk ls` shows `NateNiteProductionPollsStack`: the `mp-mgmt` SSO session had expired (`aws sso login --profile mp-mgmt`), so the app could not be instantiated (it makes read-only lookups).
- [ ] Review `make diff-polls` (the Site stack gains an export), then `make deploy-polls`.
- [ ] After deploy: page loads at `/poll1`, unknown ID shows 'poll not found' (S3 behind OAC may answer 403 for a missing object; the page treats any non-success as not found), apex and `www` still load, phone-sized viewport works.

### Deploy verification (2026-10-16)

The owner deployed with `make deploy-polls` and reported 'the page seems to work'. Checked from outside with HTTP requests (no browser, so rendered output is the owner's observation):

| Request | Result |
|---|---|
| `https://polls.natenite.net/poll1`, `/poll1/`, `/` | 200 `text/html`, the shared page (310 B) |
| `/app.js`, `/style.css` | 200, correct content types |
| `/definitions/poll1.json` | 200 `application/json`; id `poll1`, version 1, one question |
| `/definitions/nope.json` | **403** (S3 behind OAC, as predicted); the page treats any non-success as 'poll not found' |
| `/nope` | 200, the shared page (by design: the page then fails to fetch a definition) |
| `http://polls.natenite.net/poll1` | 301 to `https://polls.natenite.net/poll1` |
| `https://natenite.net/`, `https://www.natenite.net/` | 200, unaffected |
| Direct bucket URL | 403, the bucket is private |

Still resting on the owner's word, not independently confirmed:
- [ ] An unknown poll ID shows the 'Poll not found.' message in the browser.
- [ ] The page works at a phone-sized viewport.
