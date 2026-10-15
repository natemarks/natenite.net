---
type: grilling
status: open
claimed:
blocked_by: []
---

# Grill: abuse limits

## Question

What concrete limits protect the submit endpoint? Decide with the human: the per-IP WAF rate-based rule (requests per window, window length of 60/120/300/600 s, action: block or count first), the Lambda reserved concurrency cap (and therefore the function URL's maximum requests per second, 10 times that number), maximum request body size and free-text length, and what a respondent sees when throttled (429). Context: [Decide: architecture](04-decide-architecture.md) decisions 1 and 3, research/07 sections 7a and 7b, expected volume of 100 to 5,000 responses per poll.
