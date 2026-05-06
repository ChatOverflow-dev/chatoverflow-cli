"""Draft management for ChatOverflow posts.

Drafts are saved locally and pushed to the forum after user approval.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from chatoverflow_cli.config import DRAFTS_DIR


def save_draft(title: str, body: str, forum_id: str) -> dict:
    """Save a draft post to disk. Returns the draft metadata."""
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    draft_id = f"{int(time.time())}_{hash(title) & 0xFFFF:04x}"
    draft = {
        "id": draft_id,
        "title": title,
        "body": body,
        "forum_id": forum_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (DRAFTS_DIR / f"{draft_id}.json").write_text(json.dumps(draft, indent=2) + "\n")
    return draft


def list_drafts() -> list[dict]:
    """List all pending drafts, newest first."""
    if not DRAFTS_DIR.exists():
        return []
    drafts = []
    for f in sorted(DRAFTS_DIR.glob("*.json"), reverse=True):
        try:
            drafts.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return drafts


def get_draft(draft_id: str) -> dict | None:
    """Get a single draft by ID."""
    p = DRAFTS_DIR / f"{draft_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def drop_draft(draft_id: str) -> bool:
    """Delete a draft. Returns True if it existed."""
    p = DRAFTS_DIR / f"{draft_id}.json"
    if p.exists():
        p.unlink()
        return True
    return False


def clear_drafts() -> int:
    """Delete all drafts. Returns count deleted."""
    if not DRAFTS_DIR.exists():
        return 0
    count = 0
    for f in DRAFTS_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


def push_draft(draft_id: str) -> dict:
    """Post a draft to the forum and delete it locally. Returns API response.

    Raises click.ClickException on API errors.
    """
    from chatoverflow_cli import client

    draft = get_draft(draft_id)
    if not draft:
        import click
        raise click.ClickException(f"Draft '{draft_id}' not found.")

    result = client.create_question(draft["title"], draft["body"], draft["forum_id"])
    drop_draft(draft_id)
    return result
