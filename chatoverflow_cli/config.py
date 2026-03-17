import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "chatoverflow"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_API_URL = "https://www.chatoverflow.dev/api"


def _load() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")


def get_api_url() -> str:
    return os.environ.get("CHATOVERFLOW_API_URL") or _load().get("api_url") or DEFAULT_API_URL


def get_api_key() -> str | None:
    return os.environ.get("CHATOVERFLOW_API_KEY") or _load().get("api_key")


def save_api_key(api_key: str, username: str | None = None) -> None:
    data = _load()
    data["api_key"] = api_key
    if username:
        data["username"] = username
    _save(data)


def save_api_url(api_url: str) -> None:
    data = _load()
    data["api_url"] = api_url
    _save(data)
