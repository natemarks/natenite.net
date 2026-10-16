Status: ready-for-agent
Type: AFK
Blocked by: 03

# 06. Optional email stored as a separate record, with the privacy notice

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

Add the optional email field. When given, store it as its own record linked to the response by response ID; when omitted, store nothing. The email is never written to logs. The page shows a one-line notice that the address is kept until removal is requested (final legal wording is out of scope). Extend the owner script with 'purge emails older than N days' and 'delete by email address'.

## Acceptance criteria

- [ ] Entry-point tests: no email means no email record; a valid email creates an email record with the same response ID as the response; an invalid or over-254-character email is rejected with a reason.
- [ ] A test confirms no log output from the handler contains an email address.
- [ ] The page shows the optional email field and the one-line notice; skipping it works.
- [ ] The owner script purges emails older than a given age and deletes by address, with tests against the fake table.
- [ ] `make static` passes.

## Blocked by

- Blocked by 03

## User stories addressed

Spec user stories: 8, 9, 10, 40, 41, 42, 43, 53
