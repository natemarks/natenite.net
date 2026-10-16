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

- [ ] A typed `PollsSetting` loads from `config/production`, with unit tests following the existing settings tests.
- [ ] `PollsStack` is created from `PollsInput` for production and deploys after the Site stack; `cdk ls` shows `NateNiteProductionPollsStack`.
- [ ] Referencing the Site stack's web ACL adds an export to the Site stack; the regenerated Site golden file differs only by that addition.
- [ ] A golden test for the polls stack passes, and editing a poll definition or the page does not change the golden file (asset hashes are normalized by a shared test helper).
- [ ] A make target previews the polls stack diff, and another runs the unit tests and then deploys it.
- [ ] `make static` passes.
- [ ] After deploy: `https://polls.natenite.net/poll1` shows the poll and its single-choice questions; an unknown poll ID shows a 'poll not found' message; the apex and `www` sites still load.
- [ ] The page works on a phone-sized viewport.

## Blocked by

- Blocked by 01

## User stories addressed

Spec user stories: 1, 2, 14, 20-25, 32, 33, 65-68, 70, 71
