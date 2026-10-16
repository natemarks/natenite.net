Status: ready-for-agent
Type: AFK
Blocked by: 03

# 07. Poll closing time and a test that validates every poll file

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Enforce an optional closing time (UTC) on the server and show a 'poll closed' message in the page. Add a unit test that loads every real poll definition file and fails a bad one, including checking that the worst-case submission size stays within the limit.

## Acceptance criteria

- [ ] Entry-point tests with a fixed clock: a submission before the closing time is accepted; after it is rejected with a distinct reason; a poll without a closing time never closes. The status code chosen for a closed poll is documented in the tests.
- [ ] The page shows a 'poll closed' message.
- [ ] A test runs every file in the poll definitions directory and checks valid question types, unique IDs, a valid closing time, rating bounds, an integer version, and that the worst-case body (up to 4 bytes per character for every free-text cap, plus email and overhead) is under the 6 KB limit.
- [ ] A deliberately bad poll file makes the test fail (shown in the PR), and the test runs in the normal unit-test gate.
- [ ] The version number is stored on every response.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 15, 27, 28, 29, 30, 31
