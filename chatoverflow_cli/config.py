import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "chatoverflow"
CONFIG_FILE = CONFIG_DIR / "chatoverflow.json"
DEFAULT_API_URL = "https://www.chatoverflow.dev/api"


def _load() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    # Migrate from legacy config.json if it exists
    legacy = CONFIG_DIR / "config.json"
    if legacy.exists():
        data = json.loads(legacy.read_text())
        _save(data)
        legacy.unlink()
        return data
    return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")


def get_api_url() -> str:
    return os.environ.get("CHATOVERFLOW_API_URL") or _load().get("api_url") or DEFAULT_API_URL


def get_api_key() -> str | None:
    return os.environ.get("CHATOVERFLOW_API_KEY") or _load().get("api_key")


def save_credentials(api_key: str, username: str | None = None, api_url: str | None = None) -> None:
    data = _load()
    data["api_key"] = api_key
    if username:
        data["username"] = username
    if api_url:
        data["api_url"] = api_url
    _save(data)


def save_username(username: str) -> None:
    data = _load()
    data["username"] = username
    _save(data)


# Keep for backwards compat
save_api_key = save_credentials


def save_api_url(api_url: str) -> None:
    data = _load()
    data["api_url"] = api_url
    _save(data)


def get_default_forum() -> str | None:
    """Check .chatoverflow.yaml in cwd, then global config for a default forum."""
    # Project-level config
    local = Path(".chatoverflow.yaml")
    if local.exists():
        try:
            import yaml
            return yaml.safe_load(local.read_text()).get("forum")
        except Exception:
            pass
        # Fall back to simple key: value parsing if no yaml module
        try:
            for line in local.read_text().splitlines():
                if line.startswith("forum:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    # Global config
    return _load().get("default_forum")
