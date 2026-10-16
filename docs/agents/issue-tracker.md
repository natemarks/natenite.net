# Issue tracker: Local Markdown

Issues and specs (you may know a spec as a PRD) for this repo live as markdown
files in `.scratch/`. They are committed to the repo, so pushing a branch
publishes them; the repo is public on GitHub.

## Conventions

- One effort per directory: `.scratch/<effort-slug>/`. The poll app's effort
  predates this setup and lives at `.scratch/wayfinder/poll-app/`; its spec and
  issues go in that same directory.
- The spec is `<effort>/spec.md`
- Implementation issues are one file per ticket at
  `<effort>/issues/<NN>-<slug>.md`, numbered from `01`; never a combined file
- Triage state is a `Status:` line near the top of each issue file (see
  `triage-labels.md` for the role strings)
- Comments append under a `## Comments` heading at the bottom of the file

## When a skill says "publish to the issue tracker"

Create a new file under the effort directory (creating it if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path.

## Wayfinding operations

- **Map**: `<effort>/map.md` (Destination / Notes / Decisions so far /
  Frontier / Blocked / Not yet specified / Out of scope).
- **Decision ticket**: `<effort>/tickets/NN-<slug>.md` with YAML frontmatter
  `type` (research/prototype/grilling/task), `status` (`open` or `closed`),
  `claimed` (empty or who), `blocked_by` (list of ticket numbers).
- **Frontier**: tickets with `status: open`, empty `claimed`, and every
  `blocked_by` ticket closed; first by number wins.
- **Claim**: set `claimed:` and save before any work.
- **Resolve**: add a `## Resolution` section, set `status: closed`, and add a
  one-line gist plus link to the map's Decisions so far.
