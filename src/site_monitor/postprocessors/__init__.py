"""Built-in monitor postprocessors."""
import os

from ..monitor_config import PROJECT_ROOT


def _load_env() -> None:
    """Load site_monitor/.env into os.environ if present (does not override)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
