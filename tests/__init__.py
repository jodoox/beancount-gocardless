"""Test package configuration."""

from __future__ import annotations

import os

# Keep the test process quiet; dedicated subprocess tests assert the warning.
os.environ.setdefault("BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING", "1")
