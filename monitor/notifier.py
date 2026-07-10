#!/usr/bin/env python3
"""Compatibility wrapper for the packaged notifier."""
import os
import runpy
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from site_monitor.notifier import *  # noqa: F401,F403

if __name__ == "__main__":
    runpy.run_module("site_monitor.notifier", run_name="__main__")
