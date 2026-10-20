# Summarise `aws cloudwatch get-metric-data` output (read with `jq -s`: one
# document per page of results).
#
# Output: one entry per series with its value for each UTC day that has data
# (a day that is missing had none, which for these counts means zero), the
# largest day and its date, and for counts the total over the window. Series that did not
# come back complete are named in `incomplete`.
#
# The CLI writes timestamps in the machine's own timezone, for example
# 2026-10-16T20:00:00-04:00 for the day that starts at 2026-10-17T00:00:00Z,
# so every timestamp is converted to UTC before its day is taken.
def utc_day:
  (.[0:19] + "Z" | fromdateiso8601) as $local
  | .[19:] as $offset
  | (
      if $offset == "Z" or $offset == "+00:00" then 0
      else
        (($offset[1:3] | tonumber) * 3600 + ($offset[4:6] | tonumber) * 60)
        * (if $offset[0:1] == "-" then -1 else 1 end)
      end
    ) as $seconds
  | ($local - $seconds) | todate | .[0:10];

[.[].MetricDataResults[]]
| {
    metrics: (
      group_by(.Label)
      | map(
          (.[0].Label | split(": ")) as $parts
          | ([
              .[]
              | [.Timestamps, .Values]
              | transpose[]
              | {day: (.[0] | utc_day), value: .[1]}
            ] | sort_by(.day)) as $days
          | {
              kind: $parts[0],
              name: ($parts[1:] | join(": ")),
              days: $days,
              max: (if $days == [] then null else ([$days[].value] | max) end),
              max_day: (
                if $days == [] then null else ($days | max_by(.value) | .day) end
              )
            }
          + (
              if $parts[0] == "count"
              then {total: ([$days[].value] | add // 0)}
              else {}
              end
            )
        )
      | sort_by(.kind, .name)
    ),
    incomplete: (
      [.[] | select(.StatusCode != "Complete") | .Label] | unique
    )
  }
