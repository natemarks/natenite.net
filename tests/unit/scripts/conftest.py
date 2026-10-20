"""Make the owner scripts importable in tests by their bare module names."""

import sys

from config.helper import PROJECT_ROOT

SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
