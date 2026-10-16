Status: ready-for-agent

# Spec: Web polls at polls.natenite.net

## Problem Statement

I want to run simple public polls on my own domain. Each poll should have its own address (for example `polls.natenite.net/poll1`), ask a handful of questions, let a visitor answer them and optionally leave an email address, and store the results somewhere I can read later. Right now I have a static site and nothing that can accept a visitor's input.

The polls are small and personal, so the solution has to cost almost nothing at rest, need no servers or containers to look after, and not put the main site at risk. Because visitors are anonymous and the address is public, it also has to resist spam and floods, protect the optional email address, and give me a way to check periodically that nothing is going wrong.

## Solution

A visitor opens a poll's address and sees a form built from that poll's definition. They answer the questions, optionally add an email address, and submit. They get a thank-you message. They never see results.

Behind that, one small server-side function validates every submission against the poll's definition and stores it. Each poll lives as a JSON file in the repository, so adding a poll is a commit and a deploy. The page and the function are deployed together from the same commit, so what the visitor sees and what the server enforces can never drift apart.

I read results myself with a script. The data is stored under stable keys per poll and per response so that I can automate later. The optional email address is stored as a separate record from the answers so I can delete or export emails without touching the answers. For checking on health, raw CloudFront access logs are kept in cheap long-term storage and queried with saved Athena queries, and the function writes structured log lines I can query with CloudWatch Logs Insights. There are no alerts; I check periodically.

The whole thing runs as one new stack on its own CloudFront distribution at `polls.natenite.net`, reusing the existing certificate, DNS zone and web ACL. Expected running cost is about a dollar a month plus cents.

## User Stories

### Respondent

1. As a respondent, I want to open a poll at its own web address, so that I can answer it without searching for it.
2. As a respondent, I want the form to show the poll's title and questions, so that I know what I am being asked.
3. As a respondent, I want to answer single-choice questions by picking one option, so that my choice is unambiguous.
4. As a respondent, I want to answer multiple-choice questions by picking any number of options, so that I can express more than one preference.
5. As a respondent, I want to answer rating questions on a clear numeric scale, so that I can express intensity quickly.
6. As a respondent, I want to answer free-text questions in my own words, so that I can say things the options do not cover.
7. As a respondent, I want to see how many characters I have left in a free-text answer, so that I am not surprised by a limit.
8. As a respondent, I want to skip an optional email field, so that I can answer without identifying myself.
9. As a respondent, I want to leave an email address if I choose, so that the poll owner can contact me later.
10. As a respondent, I want a short notice next to the email field saying how my address is kept, so that I can decide whether to share it.
11. As a respondent, I want a clear message when I miss or mis-answer a required question, so that I can fix it before submitting.
12. As a respondent, I want to see a thank-you message after submitting, so that I know my answers were received.
13. As a respondent, I want to be told if this browser already submitted this poll, so that I do not answer twice by accident.
14. As a respondent, I want a clear "poll not found" message when the address is wrong, so that I know it is not my fault.
15. As a respondent, I want a clear "poll closed" message when a poll has passed its closing time, so that I do not fill in a form that cannot be accepted.
16. As a respondent, I want a friendly "busy, please try again in a minute" message when the service is overloaded, so that I know to retry and not give up.
17. As a respondent, I want my answers kept in the form when a submission fails, so that I do not have to retype them.
18. As a respondent, I want the page to retry a failed submission automatically a couple of times, so that a brief hiccup does not lose my answers.
19. As a respondent, I want one click to resubmit after a failure, so that recovering is easy.
20. As a respondent, I want the page to work on a phone, so that I can answer from anywhere.
21. As a respondent, I want the page to load quickly, so that I do not abandon the poll.
22. As a respondent, I want the poll address to use HTTPS under the owner's domain, so that I can trust where I am submitting.
23. As a respondent, I want the `www`-less poll address and a trailing slash to both work, so that a mistyped link still arrives.

### Poll owner

24. As the poll owner, I want to define a poll in a JSON file in the repository, so that polls are versioned and reviewable.
25. As the poll owner, I want to give each poll an ID that becomes its address, so that links are predictable.
26. As the poll owner, I want to choose from single-choice, multiple-choice, rating and free-text questions, so that I can ask what I need.
27. As the poll owner, I want to set an optional closing time on a poll, so that it stops accepting responses on a date I choose.
28. As the poll owner, I want a poll without a closing time to stay open, so that I do not have to set one.
29. As the poll owner, I want each poll definition to carry a version number that is stored with every response, so that I can tell which wording a response answered.
30. As the poll owner, I want a bad poll file to fail the checks before it can deploy, so that I never publish a poll that cannot be submitted.
31. As the poll owner, I want those checks to confirm that a poll's worst-case submission fits within the size limit, so that a long poll cannot be unsubmittable.
32. As the poll owner, I want a new poll to go live with one command that runs the checks first, so that deploying is safe and routine.
33. As the poll owner, I want a preview command that shows what a deploy would change, so that I can review it first.
34. As the poll owner, I want every response stored under a stable key by poll and response, so that my scripts can read a poll's data with one query.
35. As the poll owner, I want response IDs that sort by submission time, so that results come back in order.
36. As the poll owner, I want each response to record when it was submitted and which poll version it answered, so that I can analyze it later.
37. As the poll owner, I want answers stored by question ID in a fixed shape per question type, so that automation does not need special cases.
38. As the poll owner, I want a hashed browser token stored with each response, so that I can filter repeat submissions from one browser in my script.
39. As the poll owner, I want the server to accept repeat submissions without rejecting them, so that no genuine respondent is wrongly blocked.
40. As the poll owner, I want the email address stored as its own record linked by response ID, so that I can remove emails without touching answers.
41. As the poll owner, I want emails kept until I delete them, so that I can use them manually later.
42. As the poll owner, I want to delete emails older than a chosen age with my script, so that I can honor a retention choice.
43. As the poll owner, I want to delete the email for a given address with my script, so that I can honor a removal request.
44. As the poll owner, I want no results shown to respondents and no results page to maintain, so that the public surface stays tiny.
45. As the poll owner, I want no automatic email sent to respondents, so that there is no mailing system to run or secure.
46. As the poll owner, I want the table to survive accidental stack deletion, so that I cannot lose gathered data by tearing down infrastructure.
47. As the poll owner, I want deletion protection on the table, so that deleting it takes a deliberate extra step.

### Operator (the poll owner checking health)

48. As the operator, I want CloudFront access logs delivered to storage for the polls site, so that I can see every request, including ones blocked before they reach the function.
49. As the operator, I want those logs in JSON in a bucket that expires them after a year, so that I can read them and so that visitor IP addresses are not kept forever.
50. As the operator, I want a ready Athena table over those logs, so that I can query them without building it each time.
51. As the operator, I want saved queries for errors by day, top client IPs, and 403 and 429 responses, so that my periodic check is a routine and not an exercise.
52. As the operator, I want the function to write one structured log line per request outcome, so that I can see accepted submissions, rejections and errors.
53. As the operator, I want those log lines never to contain an email address or answer text, so that logs are not a second copy of personal data.
54. As the operator, I want the function's log group to keep entries for a year, so that its history matches the CloudFront logs.
55. As the operator, I want saved Logs Insights queries for the function's log lines, so that I can check them as easily as the CloudFront logs.
56. As the operator, I want no alarms or notifications, so that I am not paged by a hobby site.
57. As the operator, I want a clear record of what each check showed, so that I can decide whether a later phase should filter and normalize events.

### Abuse and cost protection

58. As the operator, I want a per-IP rate limit on the submit path, so that one client cannot flood it.
59. As the operator, I want that limit to apply only to submissions, so that normal page views never count against a visitor.
60. As the operator, I want a hard cap on how many submissions the function processes at once, so that a distributed flood is bounded in cost.
61. As the operator, I want requests above that cap to get a clear "too many requests" answer, so that clients and the page can react.
62. As the operator, I want the function to reject oversize bodies with a clear error before WAF blocks them generically, so that respondents see a useful message.
63. As the operator, I want free-text answers and emails capped in length, so that a single submission cannot be huge.
64. As the operator, I want the function to be reachable only through CloudFront, so that the web ACL cannot be bypassed.
65. As the operator, I want the web ACL's managed rules to keep protecting the polls site, so that common attacks are blocked at the edge.

### Maintainer and developer

66. As a maintainer, I want the polls infrastructure in its own stack on its own distribution, so that a mistake there cannot break the main site.
67. As a maintainer, I want the stack built from typed settings in the existing configuration pattern, so that it matches the other stacks.
68. As a maintainer, I want infrastructure numbers (subdomain, concurrency cap, rate limit and window) in per-environment settings, so that another environment could differ.
69. As a maintainer, I want application limits defined once and shared by the function and the poll checks, so that they can never disagree.
70. As a maintainer, I want a golden-file test of the polls stack for each environment, so that unintended template changes are caught.
71. As a maintainer, I want the golden test to ignore asset hashes, so that adding a poll does not rewrite it.
72. As a maintainer, I want the function's behavior tested through its entry point with a fake table, so that tests need no AWS credentials.
73. As a maintainer, I want the page's hashing, body-building and retry logic tested with plain Node, so that the subtle signed-request header cannot silently break.
74. As a maintainer, I want all of these checks in the existing static-check gate, so that CI protects the polls code the same way it protects the stacks.
75. As a maintainer, I want an ADR recording why the function is reached through a Function URL behind CloudFront OAC, so that nobody later swaps it for something that looks simpler.
76. As a maintainer, I want the domain terms defined in the project glossary, so that code, issues and docs use the same words.
77. As a maintainer, I want a short guide on how to add a poll, so that I can do it months later without rediscovering the steps.

## Implementation Decisions

**Architecture (see ADR 0001).**
- Submissions are handled by one small Python function exposed as a Lambda Function URL with IAM authentication, reached only through a dedicated CloudFront distribution that uses Origin Access Control. The raw function address is not callable directly.
- The browser must send a SHA-256 hash of the request body in the `x-amz-content-sha256` header, because Function URLs behind OAC do not accept unsigned payloads. The submit page therefore requires JavaScript. If a no-JavaScript form is ever required, the documented fallback is an HTTP API behind CloudFront.
- Rejected alternatives and why: HTTP API behind CloudFront (extra per-request cost, locked to CloudFront only by a shared secret, cannot attach WAF); Lambda Web Function (Node.js only, resource policy has no infrastructure-as-code resource); container platforms (always-on cost floor of roughly $7 to $36 a month, App Runner closed to new customers).
- The polls site is a second CloudFront distribution in a new stack, `PollsStack`, with its input class `PollsInput`. It depends on the existing Certificate stack (certificate, hosted zone) and the existing Site stack (web ACL). The alias record for the polls hostname goes in the existing zone.
- The existing `*.natenite.net` certificate in `us-east-1` covers the polls hostname, so no new certificate is issued.

**Poll pages.**
- A single shared page serves every poll. A small viewer-request CloudFront function rewrites extension-less paths (except the submit path) to that page. The page reads the poll ID from the address, fetches that poll's definition JSON from the same origin, and builds the form.
- Any failure to fetch a definition is shown as "poll not found". Note that private S3 behind OAC typically answers 403 for a missing object, not 404; the page must treat any non-success as not found.
- The page remembers a prior submission in the browser and says so. It generates a random browser token on first visit and sends it with each submission.
- The page retries throttled and server-error responses two or three times with backoff, keeping the form filled in, then shows a "busy, try again" message with one-click resubmit.
- A one-line privacy notice sits next to the email field: the address is kept until its removal is requested.

**Poll definitions.**
- One JSON file per poll in the repository, deployed with the site and bundled into the function. Each carries an ID, title, an integer version (assumption: stored on every response), an optional closing time in UTC, and a list of questions.
- Question types: single choice, multiple choice, rating, free text. Answer shapes are fixed: single choice is one option ID; multiple choice is a list of option IDs; rating is an integer within the question's minimum and maximum; free text is a string within a length cap. Answers are keyed by question ID.
- The function bundles the definitions from the same directory that feeds the site upload, so form and server rules come from one commit. Each new poll redeploys the function.

**Submit contract.**
- One endpoint accepts a POST containing the poll ID, the answers by question ID, an optional email address and the browser token. It is the only public write path; there is no read path.
- Success returns a created response. Invalid submissions return a client error with a machine-readable reason. An unknown poll returns not found. An oversize body returns a payload-too-large error before WAF would block it. A poll past its closing time is rejected with a distinct reason (the exact status code for a closed poll is left to implementation and must be covered by tests).
- Limits: free-text answers up to 500 characters; email up to 254 characters; the function rejects any request body over 6 KB. The shared web ACL independently blocks bodies over 8 KB.
- The closing time is enforced on the server in UTC; a stale cached page cannot submit past the deadline.
- The server accepts repeat submissions. The browser token is stored hashed on each response so repeats can be recognized later.

**Storage.**
- One DynamoDB table, on-demand billing. The partition key identifies the poll; the sort key is the record type plus a time-sortable response ID.
- A response record holds the answers by question ID, the hashed browser token, the submitted-at time and the poll definition version. When an email was given, a separate email record with the same response ID holds the address.
- The table is retained on stack deletion and has deletion protection on. Point-in-time recovery stays off, because it would retain deleted emails for up to 35 days.
- Deleting by address is a filtered scan; no index at this volume. The owner's script provides "purge emails older than N days" and "delete by email".

**Abuse limits.**
- A rate-based rule is added to the existing shared web ACL. It counts only POST requests to the submit path on the polls hostname, at 20 per 5 minutes per IP, action block. It costs about a dollar a month. This requires editing the Site stack, whose golden file changes, and makes the polls stack depend on the Site stack.
- The function has a reserved concurrency of 2, which caps the Function URL at 20 requests per second; excess requests get a 429.
- The shared ACL's managed rules apply to polls traffic, including the Core rule set's 8 KB body limit.

**Observability (phase 1).**
- No alarms or notifications.
- CloudFront standard logging delivers raw access logs, in JSON, to a bucket in the stack with a 365-day expiration. The Athena results location in that bucket expires after about 30 days.
- The stack defines the Glue database and table (with partition projection), an Athena workgroup, and saved Athena queries for errors by day, top client IPs, and 403 and 429 responses.
- The function writes one structured JSON log line per request outcome and never logs an email or answer text. Its log group retains entries for 365 days. The stack defines matching saved Logs Insights queries.
- Filtering and normalizing events across these sources is deferred to a later phase.

**Settings and configuration.**
- A new typed settings object, `PollsSetting`, loaded from per-environment JSON, holds the polls subdomain, the reserved concurrency, and the rate limit and window.
- Application limits (free-text length, email length, body size) are constants shared by the function and the poll checks.
- The new stack is added to the inventory so it deploys with the others, after the Site stack.

**Deployment and repo layout.**
- Everything lives in this repository and ships in one CDK deploy: stack, function, page and poll definitions.
- A thin make target runs the unit tests and then deploys the polls stack; a sibling target shows the diff. There is no CI deploy.
- CI's static check gains a Node setup so the page's tests can run.

**Glossary.** Use the terms defined in `CONTEXT.md`: Poll, Poll definition, Question, Response, Answer, Email record, Browser token, Closing time.

## Testing Decisions

**What makes a good test here.** Test external behavior only: what goes in at an entry point and what comes out (responses, records written, log lines, synthesized resources). Do not assert on internal helpers, call order, or how a rule is implemented. A test should still pass if the implementation is rewritten.

**Seams (as proposed; three, each the highest where its behavior can be tested).**
1. **Stack template (existing seam).** A golden-file test of the polls stack for each environment, plus the regenerated Site stack golden. Asset hashes are normalized before comparison so golden files change only for infrastructure changes. A few targeted assertions on the synthesized template cover the settings that matter beyond the golden: the function URL's IAM authentication, reserved concurrency of 2, table retention and deletion protection, 365-day log retention, and the logs bucket's expiration rules.
2. **Submit handler entry point (new).** Tests send a Function URL event with an injected in-memory fake table and a fixed clock, and assert on the HTTP response, the records written and the log lines. This covers every validation rule per question type, unknown and closed polls, oversize bodies, the email stored as a separate record, the stored browser token, time-sortable response IDs, and no personal data in logs. The same seam includes a test that loads every real poll file and checks it, including that the worst-case request body stays within the limit, so a bad poll fails CI.
3. **Page logic (new).** The pure functions that compute the body hash, build the request body and decide retry timing, tested with Node's built-in test runner, including a known SHA-256 vector.

**What is not automated.** Form rendering is checked by hand at deploy time. Behaviors that depend on real AWS (OAC with POST, WAF blocks, throttling, CloudFront log delivery) are post-deploy smoke tests, not automated seams.

**Prior art.** The golden-file parameter tests for the Certificate, Site and AppVpc stacks, with the shared helpers for case data and the update-golden flag; the settings tests under the existing config tests. The handler's fake-table approach and the Node tests are new patterns.

**Gate.** All of it runs in the existing static-check gate (formatting, lint, unit tests) so CI protects the polls code like the other stacks.

## Out of Scope

- Showing results to respondents, a results page, or an admin interface.
- Sending email to respondents, a mailing list, or SES.
- Authoring the actual poll questions.
- Wording of the privacy notice and any legal review of collecting an email address (the legal basis was not researched); this is a launch-checklist item.
- Alarms, notifications, and budget alerts.
- Filtering and normalizing events across sources into a single warning/error stream, and moving handler events into S3 (a later phase that needs real log data).
- WAF logging.
- Environments other than production.
- Deploying from CI.
- Fixing the `iac_project_url` tag typo (`natenate.net`), which would rewrite every golden file; it is a separate change.
- Server-side duplicate rejection.

## Further Notes

- Source material: the wayfinder map, its closed tickets, the research files and the build plan, all under `.scratch/wayfinder/poll-app/`; the decision on compute is recorded in `docs/adr/0001-lambda-function-url-with-cloudfront-oac.md`.
- Library: the constructs this spec relies on (Function URL OAC origin with both Lambda permissions, symlink-following assets, log delivery with JSON output, Glue, Athena and saved-query constructs) were confirmed present in `aws-cdk-lib` 2.273.0, the version now pinned (see issue 01). Asset hashes do appear in the synthesized template, including two that come from the library itself.
- Items to confirm during the build (not verified in research): that a throttled Function URL request moves the 4xx or throttle metric; that WAF-blocked requests appear in CloudFront logs as 403 with result type Error; that managed rules do not block ordinary free text; and the exact status code for a closed poll.
- Dependencies between pieces: the polls stack needs the Site stack's web ACL, so the rate rule change and the polls stack deploy together. Treat the exported ACL reference as permanent.
- Expected running cost is about $1 a month for the rate rule plus cents for compute, storage, logs and queries (prices verified against the Price List API in the pricing research).
- CloudFront logs arrive up to several times an hour and can lag by up to 24 hours; do not judge logging by the first hour.
