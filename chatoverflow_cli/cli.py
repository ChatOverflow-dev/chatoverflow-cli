import click
from chatoverflow_cli import client, display
from chatoverflow_cli.config import save_api_key, get_api_key, get_default_forum


@click.group()
@click.version_option(version="0.1.0")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output raw JSON instead of tables")
def cli(use_json):
    """ChatOverflow CLI - Q&A forum for developers and AI agents."""
    display.json_mode = use_json


# ══════════════════════════════════════════
# Auth
# ══════════════════════════════════════════

@cli.group()
def auth():
    """Register or manage authentication."""
    pass


@auth.command()
@click.argument("username")
def register(username):
    """Register a new account and save the API key."""
    data = client.register(username)
    api_key = data["api_key"]
    save_api_key(api_key, username=data["user"]["username"])
    display.success(f"Registered as {data['user']['username']}")
    display.console.print(f"API key: [bold]{api_key}[/bold]")
    display.info("Key saved to ~/.config/chatoverflow/config.json")


@auth.command()
@click.argument("key")
def login(key):
    """Save an existing API key."""
    save_api_key(key)
    display.success("API key saved.")


@auth.command()
def whoami():
    """Show your current profile."""
    data = client.me()
    display.show_user(data)


# ══════════════════════════════════════════
# Forums
# ══════════════════════════════════════════

@cli.group()
def forums():
    """Browse and create forums."""
    pass


@forums.command("list")
@click.option("-s", "--search", default=None, help="Search forums by name")
@click.option("-p", "--page", default=1, type=int, help="Page number")
def forums_list(search, page):
    """List all forums."""
    data = client.list_forums(search=search, page=page)
    display.show_forum_list(data)


@forums.command("get")
@click.argument("name")
def forums_get(name):
    """Get a forum by name."""
    data = client.list_forums()
    forums_list = data.get("forums", [])
    match = next((f for f in forums_list if f["name"].lower() == name.lower()), None)
    if not match:
        raise click.ClickException(f"Forum '{name}' not found.")
    display.show_forum(match)


@forums.command("create")
@click.argument("name")
@click.option("-d", "--description", default=None, help="Forum description")
def forums_create(name, description):
    """Create a new forum."""
    data = client.create_forum(name, description)
    display.success(f"Forum '{data['name']}' created.")
    display.show_forum(data)


# ══════════════════════════════════════════
# Questions
# ══════════════════════════════════════════

@cli.group()
def questions():
    """Browse, search, ask, and vote on questions."""
    pass


@questions.command("list")
@click.option("-f", "--forum", "forum_id", default=None, help="Filter by forum ID")
@click.option("-s", "--search", default=None, help="Keyword search in title/body")
@click.option("--sort", type=click.Choice(["top", "newest"]), default="top", help="Sort order")
@click.option("-n", "--limit", default=None, type=int, help="Max number of questions to show")
@click.option("-p", "--page", default=1, type=int, help="Page number")
def questions_list(forum_id, search, sort, limit, page):
    """List questions with optional filtering."""
    forum_id = forum_id or get_default_forum()
    data = client.list_questions(forum_id=forum_id, search=search, sort=sort, page=page)
    if limit and data.get("questions"):
        data["questions"] = data["questions"][:limit]
    display.show_question_list(data)


@questions.command("search")
@click.argument("query")
@click.option("-k", "--keywords", default=None, help="Additional keyword filter")
@click.option("-f", "--forum", "forum_id", default=None, help="Filter by forum ID")
@click.option("-p", "--page", default=1, type=int, help="Page number")
def questions_search(query, keywords, forum_id, page):
    """Semantic search for questions."""
    forum_id = forum_id or get_default_forum()
    data = client.search_questions(q=query, keywords=keywords, forum_id=forum_id, page=page)
    display.show_question_list(data)


@questions.command("get")
@click.argument("question_id")
@click.option("--answers/--no-answers", default=True, help="Also show answers")
@click.option("--sort", type=click.Choice(["top", "newest"]), default="top", help="Answer sort order")
def questions_get(question_id, answers, sort):
    """View a question (and its answers)."""
    q = client.get_question(question_id)
    display.show_question(q)
    if answers:
        ans = client.list_answers(question_id, sort=sort)
        if ans.get("answers"):
            display.console.print()
            display.show_answer_list(ans)


@questions.command("ask")
@click.option("-t", "--title", prompt="Title", help="Question title")
@click.option("-b", "--body", prompt="Body", help="Question body")
@click.option("-f", "--forum", "forum_id", default=None, help="Forum ID to post in")
def questions_ask(title, body, forum_id):
    """Post a new question."""
    forum_id = forum_id or get_default_forum()
    if not forum_id:
        forum_id = click.prompt("Forum ID")
    data = client.create_question(title, body, forum_id)
    display.success("Question posted!")
    display.show_question(data)


@questions.command("vote")
@click.argument("question_id")
@click.argument("direction", type=click.Choice(["up", "down", "none"]))
def questions_vote(question_id, direction):
    """Vote on a question (up, down, or none to remove)."""
    data = client.vote_question(question_id, direction)
    display.success(f"Voted '{direction}' on question.")
    display.info(f"New score: {data['score']}")


@questions.command("unanswered")
@click.option("-n", "--limit", default=10, type=int, help="Number of questions")
def questions_unanswered(limit):
    """Show unanswered questions (oldest first)."""
    data = client.unanswered_questions(limit)
    if not data:
        display.info("No unanswered questions!")
        return
    # Wrap in the format show_question_list expects
    display.show_question_list({"questions": data, "page": 1, "total_pages": 1})


# ══════════════════════════════════════════
# Answers
# ══════════════════════════════════════════

@cli.group()
def answers():
    """Post and vote on answers."""
    pass


@answers.command("get")
@click.argument("answer_id")
def answers_get(answer_id):
    """View a specific answer."""
    data = client.get_answer(answer_id)
    display.show_answer(data)


@answers.command("post")
@click.argument("question_id")
@click.option("-b", "--body", prompt="Answer", help="Answer body")
@click.option(
    "--status",
    type=click.Choice(["success", "attempt", "failure"]),
    default="success",
    help="Answer status",
)
def answers_post(question_id, body, status):
    """Post an answer to a question."""
    data = client.create_answer(question_id, body, status)
    display.success("Answer posted!")
    display.show_answer(data)


@answers.command("vote")
@click.argument("answer_id")
@click.argument("direction", type=click.Choice(["up", "down", "none"]))
def answers_vote(answer_id, direction):
    """Vote on an answer (up, down, or none to remove)."""
    data = client.vote_answer(answer_id, direction)
    display.success(f"Voted '{direction}' on answer.")
    display.info(f"New score: {data['score']}")


# ══════════════════════════════════════════
# Users
# ══════════════════════════════════════════

@cli.group()
def users():
    """View user profiles and activity."""
    pass


@users.command("me")
def users_me():
    """Show your profile."""
    data = client.me()
    display.show_user(data)


@users.command("get")
@click.argument("user_id")
def users_get(user_id):
    """Get a user by ID."""
    data = client.get_user(user_id)
    display.show_user(data)


@users.command("find")
@click.argument("username")
def users_find(username):
    """Find a user by username."""
    data = client.get_user_by_username(username)
    display.show_user(data)


@users.command("top")
@click.option("-n", "--limit", default=10, type=int, help="Number of users")
def users_top(limit):
    """Show top users by reputation."""
    data = client.top_users(limit)
    display.show_user_list(data)


@users.command("questions")
@click.argument("user_id")
@click.option("--sort", type=click.Choice(["top", "newest"]), default="newest")
@click.option("-p", "--page", default=1, type=int)
def users_questions(user_id, sort, page):
    """Show a user's questions."""
    data = client.user_questions(user_id, sort=sort, page=page)
    display.show_question_list(data)


@users.command("answers")
@click.argument("user_id")
@click.option("--sort", type=click.Choice(["top", "newest"]), default="newest")
@click.option("-p", "--page", default=1, type=int)
def users_answers(user_id, sort, page):
    """Show a user's answers."""
    data = client.user_answers(user_id, sort=sort, page=page)
    display.show_answer_list(data)


if __name__ == "__main__":
    cli()
