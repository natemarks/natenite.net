"""Limits shared by the submit function and the poll definition checks.

Purpose:
- Keep every size limit in one place so the function and the tests that
  validate poll definitions can never disagree.
"""

# The shared web ACL independently blocks request bodies over 8 KB, so the
# function rejects over 6 KB first and can give the respondent a clear error.
MAX_BODY_BYTES = 6 * 1024

# Free-text answers are capped in Unicode characters (code points), not bytes
# or UTF-16 units. The page library keeps a copy of this number; a test fails
# if the two differ.
MAX_TEXT_CHARS = 500
