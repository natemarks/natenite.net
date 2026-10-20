"""Limits the submit function enforces.

Purpose:
- Keep every size limit in one place.
"""

# The shared web ACL independently blocks request bodies over 8 KB, so the
# function rejects over 6 KB first and can give the respondent a clear error.
MAX_BODY_BYTES = 6 * 1024

# Free-text answers are capped in Unicode characters (code points), not bytes
# or UTF-16 units. The page library keeps a copy of this number; a test fails
# if the two differ.
MAX_TEXT_CHARS = 500

# The optional email address, in Unicode characters, after trimming.
MAX_EMAIL_CHARS = 254
