"""Built-in monitor postprocessors."""
import os

from ..monitor_config import PROJECT_ROOT


def _load_env() -> None:
    """Load monitor/.env into os.environ without replacing existing values."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
