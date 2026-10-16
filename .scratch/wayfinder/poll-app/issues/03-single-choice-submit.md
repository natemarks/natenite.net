Status: ready-for-human
Type: HITL
Blocked by: 02

# 03. A single-choice poll accepts and stores a response

## Parent PRD

`.scratch/wayfinder/poll-app/spec.md` (decision map: `map.md`; ordered plan: `build-plan.md`; compute decision: ADR 0001)

## What to build

The first complete write path. A Python submit function validates a single-choice submission against the poll definition (bundled from the same directory that feeds the site) and writes a response record. Adds the on-demand DynamoDB table (retained, deletion protection, point-in-time recovery off), the Function URL with IAM auth reached through the distribution's submit behavior using OAC, the shared limits constants, the page's submit with the body hash header and thank-you message, and an owner script that dumps one poll's responses. Node tests join the existing test gate and CI gets a Node setup step.

Human gate: deploy and verify the signed POST path on the real distribution.

## Acceptance criteria

- [ ] Entry-point tests with an in-memory fake table: a valid submission returns a created response and writes exactly one response record holding answers by question ID, submitted-at time and poll version; response IDs sort by submission time.
- [ ] Tests: an unknown option or a missing required answer is rejected with a machine-readable reason; an unknown poll returns not found; a body over 6 KB returns payload-too-large.
- [ ] Page logic tests (Node built-in runner) cover the body hash with a known SHA-256 vector and the request body builder.
- [ ] CI's static-check runs the Node tests with a pinned Node setup.
- [ ] Template assertions: the Function URL uses IAM auth, the table is retained with deletion protection, and the golden files are updated and read.
- [ ] An owner script dumps one poll's responses to JSON or CSV using a single query.
- [ ] After deploy: submitting through the page stores a record and shows a thank-you; a POST without the hash header fails; the raw function address is rejected; the table has the expected keys.

## Blocked by

- Blocked by 02

## User stories addressed

Spec user stories: 3, 12, 22, 34-37, 44-47, 64, 69, 72-74
