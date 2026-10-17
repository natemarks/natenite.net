"""Make the submit function's modules importable in tests.

The function directory is named `lambda` (a Python keyword), so it cannot be
imported as a package. It is deployed as the root of the function bundle, so
its modules are imported by their bare names, as Lambda does.
"""

import sys

from config.helper import PROJECT_ROOT

SUBMIT_DIR = str(PROJECT_ROOT / "lambda" / "submit")
if SUBMIT_DIR not in sys.path:
    sys.path.insert(0, SUBMIT_DIR)
