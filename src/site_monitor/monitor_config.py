#!/usr/bin/env python3
"""Shared monitor source and runtime path configuration."""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config.json"
RUNTIME_DIR = PROJECT_ROOT / "runtime"


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get_monitor_source(name):
    return load_config().get("monitor_sources", {}).get(name, {})


def get_rss_feeds():
    """返回 config.json 的 rss_feeds 列表,每项形如 {key, name, urls, limit}。"""
    return load_config().get("rss_feeds", [])


def runtime_path(kind, filename):
    configured = load_config().get("runtime", {})
    dirname = configured.get(f"{kind}_dir", f"runtime/{kind}")
    directory = PROJECT_ROOT / dirname
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / filename)
