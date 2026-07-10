"""Config-driven postprocessing hooks for monitor output."""
from importlib import import_module
from typing import Any, Callable

from .monitor_config import load_config


def _load_function(module_name: str, function_name: str) -> Callable[[dict, dict], dict]:
    module = import_module(module_name)
    func = getattr(module, function_name)
    if not callable(func):
        raise TypeError(f"{module_name}.{function_name} is not callable")
    return func


def get_postprocessor_specs(source_name: str) -> list[dict[str, Any]]:
    specs = load_config().get("postprocessors", {}).get(source_name, [])
    if isinstance(specs, dict):
        specs = [specs]
    if not isinstance(specs, list):
        return []
    return [spec for spec in specs if isinstance(spec, dict)]


def apply_postprocessors(source_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run configured postprocessors for a monitor source.

    A postprocessor receives a payload dict plus its options and returns a
    payload dict. This keeps filtering, translation, summarization, and future
    AI-powered cleanup outside individual monitor scripts.
    """
    result = dict(payload)
    for spec in get_postprocessor_specs(source_name):
        if not spec.get("enabled", True):
            continue
        module_name = spec.get("module")
        function_name = spec.get("function", "process")
        if not module_name:
            continue
        func = _load_function(module_name, function_name)
        processed = func(dict(result), spec.get("options", {}))
        if processed is None:
            continue
        if not isinstance(processed, dict):
            raise TypeError(f"{module_name}.{function_name} must return a dict")
        result = processed
    return result
