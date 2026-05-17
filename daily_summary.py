#!/usr/bin/env python3
"""Compatibility wrapper for the packaged daily summary."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from site_monitor.daily_summary import main


if __name__ == "__main__":
    main()
