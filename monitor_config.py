#!/usr/bin/env python3
"""Shared monitor source configuration."""
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get_monitor_source(name):
    return load_config().get("monitor_sources", {}).get(name, {})
