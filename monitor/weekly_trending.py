#!/usr/bin/env python3
"""Compatibility wrapper for the packaged weekly Trending notifier."""
import os
import runpy
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

if __name__ == "__main__":
    runpy.run_module("site_monitor.weekly_trending", run_name="__main__")
