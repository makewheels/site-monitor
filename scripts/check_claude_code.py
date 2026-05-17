#!/usr/bin/env python3
"""Compatibility wrapper for the packaged Claude Code monitor."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from site_monitor.check_claude_code import main


if __name__ == "__main__":
    main()
