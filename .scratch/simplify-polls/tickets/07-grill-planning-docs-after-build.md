---
type: grilling
status: closed
claimed: Nate Marks
blocked_by: []
---

# Grill: planning docs after the build

## Question

`.scratch/wayfinder/poll-app/` holds the original effort: a map, a spec,
ticket and issue files, research notes and a build plan (about 30 files),
committed to a public repo. `README.md`, `POLLS.md` and ADR 0001 link into it,
and this effort adds `.scratch/simplify-polls/`. Once the build is done, which
of this stays committed and linked, which is archived or deleted, and where do
the facts a future maintainer needs live (the spec's requirements, the research
citations behind ADR 0001, the closed decisions)? The branch also adds
`CONTEXT.md` and `docs/agents/` and extends `CLAUDE.md`: decide whether any of
them need to change to match the simplifications.

## Resolution

Decided with the human, one branch at a time. Facts: `.scratch/wayfinder/poll-app/`
holds 36 files (about 2,950 lines: map, spec, build plan, 15 issue files,
`issues.json` which duplicates the issue bodies, 8 decision tickets, 5 research
notes); this effort adds 8 files (about 600 lines). Only `README.md`,
`POLLS.md` (links to the spec) and ADR 0001 (cites research 05 and 06 by path)
point into it. Parts are already wrong against the decisions in this effort
(issues 11, 12, 13, the spec's log and saved-query sections, the build plan's
smoke tests). The repo is public; the production account ID in
`build-plan.md` is already committed in `config/production/environment.json`
and the golden files, and an account ID is not a credential, so it is not a new
exposure. Issue 15 (launch verification) has not run, and it and the build
plan are the launch plan.

1. **Prune, keeping the durable parts.** Keep the spec (requirements and
   implementation decisions) and the two research notes ADR 0001 cites
   (`05-container-platforms.md`, `06-verified-pricing.md`). Delete the rest of
   `.scratch/wayfinder/poll-app/` (maps, tickets, issues, `issues.json`, build
   plan, research 01, 02 and 07) and, once the refactors ship,
   `.scratch/simplify-polls/`. Rejected: keeping everything (about 3,500 lines
   of partly wrong planning text that also misleads agents, since `CLAUDE.md`
   points them at `.scratch/`); deleting all of `.scratch/` (loses the
   evidence behind the ADR).
2. **Move the survivors to `docs/polls/`:** `docs/polls/spec.md` and
   `docs/polls/research/05-container-platforms.md` and
   `06-verified-pricing.md`. `.scratch/` is a per-effort workspace by
   convention, so durable reference material does not belong there. Update
   every link to the old paths: the spec link in `README.md` and `POLLS.md`,
   the two research paths in ADR 0001, and the spec's own "source material"
   line. Do not rewrite the spec; add a short **"Changes since this spec"**
   note at its top listing what is superseded (the access-log and Athena
   stories, 48 to 51 and 57; the saved queries; the body-budget check; the
   Crockford response IDs; the old log fields) and pointing to `POLLS.md` for
   current behaviour. Rejected: leaving them under `.scratch/`; rewriting the
   spec to match the code (more work, and the original record is lost).
3. **Sequence.**
   1. Before launch verification, update issue 15 and the build plan to the
      simplified design: drop the access-log checks (issue 15's question about
      WAF blocks as 403s in the CloudFront logs, issue 12 and the build plan's
      log-delivery smoke tests) and add a smoke test that `make check-polls`
      runs and returns a summary.
   2. After launch verification passes, as the last slice, delete the planning
      files.
   3. Tag the branch tip before deleting and put the tag name in the "Changes
      since this spec" note, so the files stay recoverable if the branch is
      squash-merged and deleted (a bare commit hash can become unreachable from
      `main`).
   4. Make a one-line update to `docs/agents/issue-tracker.md`, which names
      `.scratch/wayfinder/poll-app/` as the poll app's effort directory.
   5. Delete `.scratch/simplify-polls/` once the refactors ship; the PR
      description carries the decision summary and the tag.
   Rejected: deleting everything now (could prune the launch checklist before
   it has been used).
4. **No change needed to `CONTEXT.md`, ADR 0001 or `CLAUDE.md`.** None of the
   simplifications touches a glossary term or contradicts the ADR, and the
   `CLAUDE.md` pointer to `.scratch/<effort>/` concerns future efforts. Not
   ADR-worthy: dropping the access-log layer is easy to reverse, so it fails
   the "hard to reverse" test and is recorded in
   [Grill: observability layers](01-grill-observability-layers.md) instead.
