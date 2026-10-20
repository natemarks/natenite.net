# Summarise the function's log lines (read with `jq -s`, one object per line).
#
# Output: how many requests and how they ended, rejections counted by reason
# (most frequent first), and every error-level line, newest first.
{
  requests: length,
  outcomes: (
    group_by(.outcome)
    | map({key: .[0].outcome, value: length})
    | from_entries
  ),
  rejections_by_reason: (
    [.[] | select(.outcome == "rejected")]
    | group_by(.reason)
    | map({reason: .[0].reason, count: length})
    | sort_by(-.count, .reason)
  ),
  errors: ([.[] | select(.level == "ERROR")] | sort_by(.timestamp) | reverse)
}
