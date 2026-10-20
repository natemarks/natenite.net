# Turn `aws logs filter-log-events` output into the function's own log lines,
# one JSON object per line, each with the event's timestamp added.
#
# Platform lines (START, END, REPORT) are not JSON and are skipped. The input
# can be one response or several pages' worth.
.events[]?
| .timestamp as $ms
| (.message | fromjson? | objects)
| . + {timestamp: (($ms / 1000) | floor | todate)}
