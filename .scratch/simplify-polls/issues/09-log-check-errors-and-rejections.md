Status: ready-for-agent
Type: AFK
Blocked by: 04, 07

# 09. Log check part 1: errors and rejections from the function's log

## Parent PRD

`.scratch/simplify-polls/spec.md` (decisions and rationale: the closed tickets under `.scratch/simplify-polls/tickets/`; architecture fixed by ADR 0001)

## What to build

Add the first half of the log check. `make fetch-logs [days=90]` downloads the function's log lines for the window, one JSON object per line, into a git-ignored working folder (`.polls-check/`) using the pinned log group name and changing nothing in AWS. A stored jq program turns the local copy into a JSON summary: every error-level line and the rejections counted by reason. `make check-polls [days=90]` runs the fetch and prints the summary (the metrics half is added by the next slice). A fixture test runs the jq program over fixture lines (accepted, rejected with several reasons, failed with an error type) and asserts the summary, in the normal unit-test gate. See [Grill: owner scripts and docs](../tickets/06-grill-owner-scripts-and-docs.md), decision 1.

## Acceptance criteria

- [x] Fixture lines covering accepted, rejected (at least two reasons) and failed requests produce the expected summary; the test runs in `make unit-test` and in the CI static-check.
- [x] The CI runner is confirmed to have jq, or the workflow gains an install step (stated in the PR).
- [x] `make fetch-logs` takes a `days` argument defaulting to 90, writes JSON lines, and the folder is git-ignored.
- [x] `make check-polls` prints the summary and exits non-zero if the fetch fails; it never writes to AWS.
- [x] The summary lists error-level lines and rejection counts by reason; it contains no email, answer text or token because the log never holds them.
- [x] The fetch is verified against the real log group in the deploy slice, not here.
- [x] `make static` passes.

## Blocked by

- Blocked by [Trim the function's log line and consolidate its logging tests](04-trim-the-log-line.md)
- Blocked by [Pin the log group name and drop the saved queries](07-pin-log-group-and-drop-saved-queries.md)

## User stories addressed

Spec user stories: 1, 2, 3, 7, 8, 9, 36, 37, 43

## Comments

Done (uncommitted). New files: `scripts/jq/polls_log_lines.jq`,
`scripts/jq/polls_log_summary.jq`, `tests/unit/scripts/test_polls_log_check.py`.
Changed: `Makefile` (two targets), `.gitignore`.

- **`make fetch-logs [days=90]`:** derives the log group and region from
  `PollsInput` (so the name formula is not repeated), calls
  `aws logs filter-log-events --start-time <now - days>` and pipes it through
  `polls_log_lines.jq` into `.polls-check/handler.jsonl`. It writes to a temp
  file and moves it into place only on success, so a failed fetch leaves the
  previous copy alone. It reads only; nothing in AWS changes. The folder is in
  `.gitignore`.
- **`make -s check-polls [days=90]`:** runs the fetch (so a failed fetch stops
  it with a non-zero exit and no summary), then prints one JSON summary with
  `polls_log_summary.jq`: `requests`, `outcomes`, `rejections_by_reason` (most
  frequent first, ties alphabetical) and `errors` (every error-level line,
  newest first). Use `make -s` to keep stdout to the JSON.
- **Two small additions to the plan, both needed:** each fetched line gains a
  `timestamp` (the CloudWatch event time, ISO, UTC), because the trimmed log
  line no longer carries a time of its own and an error list without times is
  hard to troubleshoot from; and the summary includes the outcome counts, which
  cost nothing. Platform lines (START, END, REPORT) are skipped.
- **Fixture tests (5, in the normal unit-test gate):** platform lines skipped
  and the timestamp added (times worked out by hand with `date`); several pages
  of output read; an empty window; the full summary asserted for a mixed set of
  accepted, rejected (several reasons) and failed lines; an empty summary.
  A mutation run broke the jq programs 12 ways and the tests caught 11. The
  twelfth (dropping the explicit alphabetical tie-break) is an equivalent
  change, because `group_by` already orders reasons and jq's sort is stable.
- **CI has jq, no install step needed:** the GitHub runner image readmes list
  jq 1.7 on Ubuntu 24.04 (what `ubuntu-latest` uses today) and jq 1.8.1 on
  Ubuntu 26.04 (what the page says it moves to in November 2026). Local jq is
  1.8.1; the programs use only long-standing jq features, but the first CI run
  is the first run under 1.7.
- **End-to-end against a stub `aws`:** the recipe passed the expected region,
  log group and start time, merged two pages, printed clean JSON on stdout with
  nothing on stderr, failed with exit 2 and no summary when `aws` failed while
  keeping the previous copy, and defaulted to 90 days.
- `make static` and `make static-check` exit 0: pylint 10.00/10, 255 Python
  tests (250 before, plus 5) and 41 Node tests. The new test file had to be
  marked intent-to-add (`git add -N`) for the Makefile's `git ls-files` lint to
  see it; black then reformatted it.
- **Still unverified (deploy slice):** the real `aws logs filter-log-events`
  output shape (the stub assumes `events[].timestamp` and `events[].message`
  and that the CLI merges pages), against the real log group.
