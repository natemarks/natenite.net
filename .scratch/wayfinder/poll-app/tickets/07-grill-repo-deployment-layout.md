---
type: grilling
status: open
claimed:
blocked_by: []
---

# Grill: repo and deployment layout

## Question

Where does the poll code live and how does it deploy? The [Decide: architecture](04-decide-architecture.md) decisions imply one repo: the poll definitions, shared page, submit Lambda and CDK stack are deployed together in one CDK deploy (definitions bundled into the Lambda and uploaded to S3). Confirm or revise that against the earlier advice to keep app code in a separate repo, and decide: directory layout (for example `polls/`, `lambda/`, `site/`), new stack and input class names following the Input/Stack pattern, how the Lambda and page assets are built and tested, golden-test and unit-test expectations, and how a new poll gets deployed (`make` target, CI).
