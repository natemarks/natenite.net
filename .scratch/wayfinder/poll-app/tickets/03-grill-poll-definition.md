---
type: grilling
status: closed
claimed: nate (grilling session)
blocked_by: []
---

# Grill: poll definition and results access

## Question

How are polls defined and how are results read? Decide with the human, one question at a time: where poll definitions live (JSON in a repo, deployed with the site, or data in storage), supported question types (single choice, multi choice, free text, rating), whether respondents see results after submitting, who reads results and how (console, export, a private page), expected volume per poll, and what the optional email is for.

## Resolution

Confirmed by the human at the end of the grilling session. Decisions:

1. **Email purpose:** option A. Stored for the owner's manual use later; no automation, no SES, no follow-up system, no mailing list in this project.
2. **Results reader:** option A. Owner only, via console or a script dumping a poll to CSV/JSON. No admin page, no auth system. **Constraint:** data must be predictably organized (stable keys per poll and response, consistent shape) so automation can be added later.
3. **Results shown to respondents:** option A. None. Respondents get a thank-you only; the public API is write-only, no read path.
4. **JavaScript:** option A. JavaScript is acceptable; the form may POST via `fetch` and show the thank-you inline. Keeps Lambda Function URL + CloudFront OAC (client-computed `x-amz-content-sha256`) on the table; no plain-form requirement.
5. **Poll definitions:** option A. JSON files in the repo (e.g. `polls/poll1.json`), deployed with the static site; version-controlled, no database read path. Lambda validates submissions against a trusted copy. New poll = commit + deploy.
6. **Question types:** option C. Single choice, multiple choice, rating, free text. Fixed answer shapes for predictable data: single = one option ID; multi = list of option IDs; rating = integer within the question's min/max; free text = string with a length cap. Answers keyed by question ID.
7. **Volume:** plan for about 100 to 5,000 responses per poll (modest, publicly posted). Cost stays near zero on Lambda + DynamoDB; basic per-IP rate rule and a Lambda concurrency cap suffice; no queueing or batching.
8. **Duplicates:** soft dedupe. Page remembers a prior submission (localStorage) and says so; server rejects nothing. Each response also stores a random browser token (hash) so the owner's script can filter repeats later; stricter server-side enforcement can be added without changing the data shape.
9. **Email storage:** option B. Separate record linked by response ID, no TTL (kept until the owner deletes it). Owner script gets "purge emails older than N days" and "delete by email". Point-in-time recovery stays off (it would retain deleted emails up to 35 days). Form carries a one-line privacy notice saying the address is kept until removal is requested.
10. **Lifecycle:** option B. Optional `closesAt` (UTC) in the poll JSON, enforced server-side; polls without it stay open. No scheduled opening (deploy time controls go-live).
