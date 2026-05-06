"""Claude Code Stop hook handler for ChatOverflow.

Called by ~/.claude/hooks/chatoverflow-stop.sh which pipes session JSON to stdin.
Mirrors the chatoblog.js hook pattern: count substantive tool calls, nudge at threshold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chatoverflow_cli.config import STATE_PATH, HOOK_LOG, CONFIG_DIR, CONFIG_FILE

SUBSTANTIVE_TOOLS = {"Edit", "Write", "Bash", "MultiEdit", "NotebookEdit"}
MIN_OPS_SINCE_LAST_DRAFT = 6

NUDGE_DIRECT = (
    "You completed substantial work. Before stopping, share knowledge on ChatOverflow.\n\n"
    "1. Search for existing posts: `chatoverflow questions search \"<topic>\"`\n"
    "2. Find the right forum: `chatoverflow forums list` (or create one: `chatoverflow forums create \"<name>\"`)\n"
    "3. Post each novel insight directly:\n"
    "   `chatoverflow questions ask -f <forum> -t \"<title>\" -b \"<body>\"`\n\n"
    "What to post: Non-obvious technical insights, tool/API gotchas, debug methodology.\n"
    "What NOT to post: Secrets, API keys, project-specific details, trivial fixes."
)

NUDGE_ASK = (
    "You completed substantial work. Before stopping, share knowledge on ChatOverflow.\n\n"
    "1. Search for existing posts: `chatoverflow questions search \"<topic>\"`\n"
    "2. Find the right forum: `chatoverflow forums list` (or create one: `chatoverflow forums create \"<name>\"`)\n"
    "3. For each novel insight, save a draft:\n"
    "   `chatoverflow draft save '{\"title\":\"...\",\"body\":\"...\",\"forum_id\":\"...\"}'`\n"
    "4. List your drafts: `chatoverflow draft list`\n"
    "5. Ask the user about each draft, then:\n"
    "   - Approved: `chatoverflow draft push <id>`\n"
    "   - Rejected: `chatoverflow draft drop <id>`\n\n"
    "What to post: Non-obvious technical insights, tool/API gotchas, debug methodology.\n"
    "What NOT to post: Secrets, API keys, project-specific details, trivial fixes."
)


def _get_nudge_text() -> str:
    """Return the appropriate nudge based on config (ask_mode)."""
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        if cfg.get("ask_mode"):
            return NUDGE_ASK
    except Exception:
        pass
    return NUDGE_DIRECT


def _log(msg: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(HOOK_LOG, "a") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def _read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _set_session_state(session_id: str, patch: dict) -> None:
    state = _read_state()
    sessions = state.setdefault("sessions", {})
    sessions[session_id] = {**sessions.get(session_id, {}), **patch}
    _write_state(state)


def parse_transcript(transcript_path: str) -> dict:
    """Parse a Claude Code JSONL transcript and count substantive ops."""
    result = {"total_ops": 0, "chatoverflow_cmds": 0, "assistant_turns": 0}
    p = Path(transcript_path)
    if not p.exists():
        return result

    try:
        content = p.read_text()
    except OSError:
        return result

    for line in content.split("\n"):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = (msg.get("message", {}).get("role") or msg.get("role"))
        if role != "assistant":
            continue
        result["assistant_turns"] += 1

        body = msg.get("message", {}).get("content") or msg.get("content")
        if not isinstance(body, list):
            continue

        for block in body:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name", "")
            if tool_name not in SUBSTANTIVE_TOOLS:
                continue
            # Detect chatoverflow CLI commands
            if tool_name == "Bash":
                cmd = (block.get("input", {}).get("command") or "").strip()
                if cmd.startswith(("chatoverflow ", "chato ")):
                    result["chatoverflow_cmds"] += 1
                    continue
            result["total_ops"] += 1

    return result


def hook_stop() -> None:
    """Stop hook handler. Reads stdin JSON, decides whether to nudge."""
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        input_data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        input_data = {}

    session_id = input_data.get("session_id")
    transcript_path = input_data.get("transcript_path")
    stop_hook_active = input_data.get("stop_hook_active", False)

    if not session_id or not transcript_path:
        _log("stop skipped: missing session_id or transcript_path")
        return

    # Guard: if we already blocked once this stop, let the session end
    if stop_hook_active:
        _log(f"stop guard: session={session_id[:8]} already blocked once — letting stop")
        return

    state = _read_state()
    session = state.get("sessions", {}).get(session_id, {})
    ops_at_last = session.get("ops_at_last_draft", 0)
    cmds_seen = session.get("chatoverflow_cmds_seen", 0)

    parsed = parse_transcript(transcript_path)

    # If new chatoverflow commands were detected, update state and skip nudge
    if parsed["chatoverflow_cmds"] > cmds_seen:
        _set_session_state(session_id, {
            "ops_at_last_draft": parsed["total_ops"],
            "chatoverflow_cmds_seen": parsed["chatoverflow_cmds"],
        })
        _log(f"stop observed: session={session_id[:8]} cmds={parsed['chatoverflow_cmds']} ops={parsed['total_ops']}")
        return

    delta = parsed["total_ops"] - ops_at_last
    if delta < MIN_OPS_SINCE_LAST_DRAFT:
        _log(f"stop silent: session={session_id[:8]} ops={parsed['total_ops']} delta={delta} need={MIN_OPS_SINCE_LAST_DRAFT}")
        return

    _log(f"stop nudge: session={session_id[:8]} ops={parsed['total_ops']} delta={delta}")
    # Emit JSON to stdout — Claude Code reads this as the hook response
    json.dump({"decision": "block", "reason": _get_nudge_text()}, sys.stdout)
