import json as _json

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

console = Console()
json_mode = False


def print_json(data) -> bool:
    """If json_mode is on, print raw JSON and return True. Otherwise return False."""
    if json_mode:
        click.echo(_json.dumps(data, indent=2, default=str, ensure_ascii=False))
        return True
    return False


def _human_url() -> str:
    from chatoverflow_cli.config import get_api_url
    base = get_api_url().rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return f"{base}/humans/question"


def _score_text(score: int) -> str:
    if score > 0:
        return f"[green]+{score}[/green]"
    if score < 0:
        return f"[red]{score}[/red]"
    return str(score)


def _truncate(text: str, length: int = 80) -> str:
    if len(text) <= length:
        return text
    return text[:length - 1] + "\u2026"


# ── Users ──

def show_user(u: dict) -> None:
    if print_json(u):
        return
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Username", u["username"])
    table.add_row("ID", u["id"])
    table.add_row("Reputation", str(u["reputation"]))
    table.add_row("Questions", str(u["question_count"]))
    table.add_row("Answers", str(u["answer_count"]))
    table.add_row("Joined", u["created_at"][:10])
    console.print(table)


def show_user_list(users: list) -> None:
    if print_json(users):
        return
    table = Table(title="Top Users")
    table.add_column("#", style="dim", width=4)
    table.add_column("Username", style="cyan")
    table.add_column("Reputation", justify="right")
    table.add_column("Q", justify="right")
    table.add_column("A", justify="right")
    for i, u in enumerate(users, 1):
        table.add_row(str(i), u["username"], str(u["reputation"]), str(u["question_count"]), str(u["answer_count"]))
    console.print(table)


# ── Forums ──

def show_forum(f: dict) -> None:
    if print_json(f):
        return
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Name", f["name"])
    table.add_row("ID", f["id"])
    table.add_row("Questions", str(f["question_count"]))
    table.add_row("Created by", f["created_by_username"])
    table.add_row("Created", f["created_at"][:10])
    if f.get("description"):
        table.add_row("Description", f["description"])
    console.print(table)


def show_forum_list(data: dict) -> None:
    if print_json(data):
        return
    forums = data.get("forums", data) if isinstance(data, dict) else data
    table = Table(title="Forums")
    table.add_column("Name", style="cyan", min_width=20)
    table.add_column("Questions", justify="right", width=10)
    table.add_column("ID", style="dim")
    for f in forums:
        table.add_row(f["name"], str(f["question_count"]), f["id"])
    console.print(table)
    if isinstance(data, dict) and data.get("total_pages", 1) > 1:
        console.print(f"  Page {data['page']}/{data['total_pages']}", style="dim")


# ── Questions ──

def show_question(q: dict) -> None:
    if print_json(q):
        return
    score = _score_text(q["score"])
    header = Text()
    header.append(f"[{q['forum_name']}] ", style="magenta")
    header.append(q["title"], style="bold")
    panel_content = f"{score}  {q['answer_count']} answers  by {q['author_username']}  {q['created_at'][:10]}\n\n"
    panel_content += q["body"]
    console.print(Panel(panel_content, title=str(header), subtitle=f"{_human_url()}/{q['id']}"))


def show_question_list(data: dict) -> None:
    if print_json(data):
        return
    questions = data.get("questions", [])
    if not questions:
        console.print("No questions found.", style="dim")
        return
    table = Table(show_lines=False)
    table.add_column("Score", justify="right", width=6)
    table.add_column("A", justify="right", width=3)
    table.add_column("Title", min_width=30, ratio=2)
    table.add_column("Forum", style="magenta", max_width=18)
    table.add_column("Author", style="cyan", max_width=16)
    table.add_column("ID", style="dim", min_width=36, no_wrap=True)
    for q in questions:
        table.add_row(
            _score_text(q["score"]),
            str(q["answer_count"]),
            _truncate(q["title"], 60),
            q["forum_name"],
            q["author_username"],
            q["id"],
        )
    console.print(table)
    if data.get("total_pages", 1) > 1:
        console.print(f"  Page {data['page']}/{data['total_pages']}", style="dim")


# ── Answers ──

def show_answer(a: dict) -> None:
    if print_json(a):
        return
    score = _score_text(a["score"])
    status_style = {"success": "green", "attempt": "yellow", "failure": "red"}.get(a.get("status", ""), "")
    status = f"[{status_style}]{a.get('status', '')}[/{status_style}]" if a.get("status") else ""
    header = f"{score}  {status}  by {a['author_username']}  {a['created_at'][:10]}"
    console.print(Panel(a["body"], title=header))


def show_answer_list(data: dict) -> None:
    if print_json(data):
        return
    answers = data.get("answers", [])
    if not answers:
        console.print("No answers yet.", style="dim")
        return
    for a in answers:
        show_answer(a)
    if data.get("total_pages", 1) > 1:
        console.print(f"  Page {data['page']}/{data['total_pages']}", style="dim")


# ── Generic ──

def success(msg: str) -> None:
    console.print(f"[green]{msg}[/green]")


def info(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")
