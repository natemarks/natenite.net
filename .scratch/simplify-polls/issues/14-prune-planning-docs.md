Status: ready-for-human
Type: HITL
Blocked by: 11, 12, 13, launch verification

# 14. Prune the planning docs and retire this effort

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

After launch verification of the poll app has passed, prune the planning documents: tag the branch tip; move the spec and the two research notes the architecture decision record cites into the reference docs folder (`docs/polls/`); add a "Changes since this spec" note at the top of the spec naming the tag and listing what is superseded (the access-log and Athena stories, the saved queries, the size-budget check, the Crockford response IDs and the old log fields) and pointing to the owner guide for current behaviour; update every link to the moved files (README, owner guide, ADR 0001, the spec's own source-material line); delete the rest of `.scratch/wayfinder/poll-app/` and make the one-sentence update in the tracker doc that names that directory; finally delete this effort's own folder. The PR description carries the decision summary and the tag. See [Grill: planning docs after the build](../tickets/07-grill-planning-docs-after-build.md).

## Acceptance criteria

- [ ] The launch-verification issue of the earlier effort is closed with a passing result before anything is deleted (human gate).
- [ ] A tag exists on the branch tip before deletion and is named in the spec's note.
- [ ] The spec and research notes 05 and 06 live under `docs/polls/`, every link to them resolves, and the spec carries the "Changes since this spec" note.
- [ ] The remaining earlier planning files and this effort's folder are deleted; the tracker doc no longer names the removed directory.
- [ ] The PR description summarises the decisions and links the tag.
- [ ] `make static` passes.

## Blocked by

- Blocked by [Owner guide and README match the simplified design](11-owner-guide-matches-the-design.md)
- Blocked by [Update the launch-verification issue and build plan](12-update-the-launch-plan.md)
- Blocked by [Deploy and verify the simplified stack](13-deploy-and-verify.md)
- Launch verification of the poll app passing (the earlier effort's final issue)

## User stories addressed

Spec user stories: 38, 39, 40, 41
