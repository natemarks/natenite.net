"""Contract between the submit function's limits and the page library.

Purpose:
- The page cannot import the function's Python constants, so it keeps its own
  copy of each limit it needs. This test fails if a copy drifts.
"""

import re

import pytest

import limits
from config.helper import PROJECT_ROOT

PAGE_LIBRARY = PROJECT_ROOT / "site" / "polls" / "lib.js"


@pytest.mark.unit
def test_page_library_text_limit_matches_the_function_limit():
    """The page counts down from the same number the server enforces."""
    source = PAGE_LIBRARY.read_text(encoding="utf-8")

    match = re.search(r"var MAX_TEXT_CHARS = (\d+);", source)

    assert match, "lib.js must define `var MAX_TEXT_CHARS = <number>;`"
    assert int(match.group(1)) == limits.MAX_TEXT_CHARS
