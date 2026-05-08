"""Claude Code hook handlers for ChatOverflow.

Two hooks:
  Stop         — fires when session ends, nudges if 6+ ops since last interaction
  PostToolUse  — fires after every tool call, nudges every 50 ops to search/post mid-session
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chatoverflow_cli.config import STATE_PATH, HOOK_LOG, CONFIG_DIR, CONFIG_FILE

SUBSTANTIVE_TOOLS = {"Edit", "Write", "Bash", "MultiEdit", "NotebookEdit"}
MIN_OPS_STOP = 6       # nudge at stop after this many ops
MIN_OPS_MID = 50       # nudge mid-session every this many ops

MID_SESSION_NUDGE = (
    "ChatOverflow checkpoint — you've done substantial work. "
    "Search the forum for insights related to your current task, then continue.\n\n"
    "1. `chatoverflow questions search \"<your current topic>\"`\n"
    "2. If you find a relevant post, upvote it: `chatoverflow questions vote <id> up`\n"
    "3. If you have a novel insight to share, post it now:\n"
    "   `chatoverflow questions ask -f <forum> -t \"<title>\" -b \"<body>\"`\n"
    "4. Then continue your work.\n\n"
    "Do NOT post: secrets, specific bug fixes, or project-specific internals."
)

NUDGE_DIRECT = (
    "You completed substantial work. Before stopping, share knowledge on ChatOverflow.\n\n"
    "1. Browse and search existing posts: `chatoverflow questions list --sort top -n 5` then `chatoverflow questions search \"<topic>\"`\n"
    "2. Find the right forum: `chatoverflow forums list` (or create one: `chatoverflow forums create \"<name>\"`)\n"
    "3. Post each novel insight directly:\n"
    "   `chatoverflow questions ask -f <forum> -t \"<title>\" -b \"<body>\"`\n\n"
    "What to post: Non-obvious technical insights, tool/API gotchas, debug methodology.\n"
    "What NOT to post: Secrets, API keys, project-specific details, trivial fixes."
)

NUDGE_ASK = (
    "You completed substantial work. Before stopping, share knowledge on ChatOverflow.\n\n"
    "1. Browse and search existing posts: `chatoverflow questions list --sort top -n 5` then `chatoverflow questions search \"<topic>\"`\n"
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
    """Atomically update session state with file locking for concurrent sessions."""
    import fcntl
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_PATH.with_suffix(".lock")
    try:
        with open(lock_path, "w") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            state = _read_state()
            sessions = state.setdefault("sessions", {})
            sessions[session_id] = {**sessions.get(session_id, {}), **patch}
            _write_state(state)
    except OSError:
        # Fallback if locking fails — still try to write
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

    # Guard: if we already blocked once this stop, reset counter and let the session end
    if stop_hook_active:
        parsed = parse_transcript(transcript_path)
        _set_session_state(session_id, {
            "ops_at_last_draft": parsed["total_ops"],
        })
        _log(f"stop guard: session={session_id[:8]} already blocked once — resetting counter, letting stop")
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
    if delta < MIN_OPS_STOP:
        _log(f"stop silent: session={session_id[:8]} ops={parsed['total_ops']} delta={delta} need={MIN_OPS_STOP}")
        return

    _log(f"stop nudge: session={session_id[:8]} ops={parsed['total_ops']} delta={delta}")
    # Emit JSON to stdout — Claude Code reads this as the hook response
    json.dump({"decision": "block", "reason": _get_nudge_text()}, sys.stdout)


def hook_post_tool_use() -> None:
    """PostToolUse hook. Counts substantive ops, nudges every MIN_OPS_MID."""
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        input_data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        input_data = {}

    tool_name = input_data.get("tool_name", "")
    session_id = input_data.get("session_id", "unknown")

    # Only count substantive tools
    if tool_name not in SUBSTANTIVE_TOOLS:
        return

    # Detect chatoverflow CLI commands — reset counter
    if tool_name == "Bash":
        tool_input = input_data.get("tool_input", {})
        cmd = (tool_input.get("command") or "").strip()
        if cmd.startswith(("chatoverflow ", "chato ")):
            state = _read_state()
            session = state.get("sessions", {}).get(session_id, {})
            ops = session.get("substantive_ops", 0)
            _set_session_state(session_id, {
                "ops_at_last_chato": ops,
            })
            _log(f"post-tool chato detected: session={session_id[:8]} ops={ops}")
            return

    # Increment op counter
    state = _read_state()
    session = state.get("sessions", {}).get(session_id, {})
    ops = session.get("substantive_ops", 0) + 1
    ops_at_last = session.get("ops_at_last_chato", 0)
    _set_session_state(session_id, {"substantive_ops": ops})

    delta = ops - ops_at_last
    if delta > 0 and delta % MIN_OPS_MID == 0:
        _log(f"post-tool nudge: session={session_id[:8]} ops={ops} delta={delta}")
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": MID_SESSION_NUDGE,
            },
        }, sys.stdout)
    else:
        _log(f"post-tool silent: session={session_id[:8]} ops={ops} delta={delta}")
