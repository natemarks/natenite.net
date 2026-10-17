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

# Room kept free in the request body when checking that a poll can always be
# submitted: the optional email address (up to 254 characters), the browser
# token, and the JSON envelope fields the later slices add around the answers.
RESERVED_BODY_BYTES = 1536
