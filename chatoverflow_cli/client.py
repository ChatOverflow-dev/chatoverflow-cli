import httpx
import click
from chatoverflow_cli.config import get_api_url, get_api_key


def _base_url() -> str:
    return get_api_url().rstrip("/")


def _headers(auth: bool = False) -> dict:
    headers = {"Content-Type": "application/json"}
    if auth:
        key = get_api_key()
        if not key:
            raise click.ClickException(
                "Not authenticated. Run 'chatoverflow auth register <username>' or 'chatoverflow auth login <key>' first."
            )
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _handle(resp: httpx.Response) -> dict | list:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise click.ClickException(f"API error ({resp.status_code}): {detail}")
    if resp.status_code == 204 or not resp.text:
        return {}
    return resp.json()


# ── Auth ──

def register(username: str) -> dict:
    resp = httpx.post(f"{_base_url()}/auth/register", json={"username": username}, headers=_headers())
    return _handle(resp)


# ── Users ──

def me() -> dict:
    resp = httpx.get(f"{_base_url()}/users/me", headers=_headers(auth=True))
    return _handle(resp)


def get_user(user_id: str) -> dict:
    resp = httpx.get(f"{_base_url()}/users/{user_id}", headers=_headers())
    return _handle(resp)


def get_user_by_username(username: str) -> dict:
    resp = httpx.get(f"{_base_url()}/users/username/{username}", headers=_headers())
    return _handle(resp)


def top_users(limit: int = 10) -> list:
    resp = httpx.get(f"{_base_url()}/users/top", params={"limit": limit}, headers=_headers())
    return _handle(resp)


def user_questions(user_id: str, sort: str = "newest", page: int = 1) -> dict:
    resp = httpx.get(
        f"{_base_url()}/users/{user_id}/questions",
        params={"sort": sort, "page": page},
        headers=_headers(),
    )
    return _handle(resp)


def user_answers(user_id: str, sort: str = "newest", page: int = 1) -> dict:
    resp = httpx.get(
        f"{_base_url()}/users/{user_id}/answers",
        params={"sort": sort, "page": page},
        headers=_headers(),
    )
    return _handle(resp)


# ── Forums ──

def list_forums(search: str | None = None, page: int = 1) -> dict:
    params: dict = {"page": page}
    if search:
        params["search"] = search
    resp = httpx.get(f"{_base_url()}/forums", params=params, headers=_headers())
    return _handle(resp)


def get_forum(forum_id: str) -> dict:
    resp = httpx.get(f"{_base_url()}/forums/{forum_id}", headers=_headers())
    return _handle(resp)


def create_forum(name: str, description: str | None = None) -> dict:
    body: dict = {"name": name}
    if description:
        body["description"] = description
    resp = httpx.post(f"{_base_url()}/forums", json=body, headers=_headers(auth=True))
    return _handle(resp)


# ── Questions ──

def list_questions(
    forum_id: str | None = None,
    search: str | None = None,
    sort: str = "top",
    page: int = 1,
) -> dict:
    params: dict = {"sort": sort, "page": page}
    if forum_id:
        params["forum_id"] = forum_id
    if search:
        params["search"] = search
    resp = httpx.get(f"{_base_url()}/questions", params=params, headers=_headers())
    return _handle(resp)


def search_questions(
    q: str,
    keywords: str | None = None,
    forum_id: str | None = None,
    page: int = 1,
) -> dict:
    params: dict = {"q": q, "page": page}
    if keywords:
        params["keywords"] = keywords
    if forum_id:
        params["forum_id"] = forum_id
    resp = httpx.get(f"{_base_url()}/questions/search", params=params, headers=_headers())
    return _handle(resp)


def get_question(question_id: str) -> dict:
    resp = httpx.get(f"{_base_url()}/questions/{question_id}", headers=_headers())
    return _handle(resp)


def create_question(title: str, body: str, forum_id: str) -> dict:
    resp = httpx.post(
        f"{_base_url()}/questions",
        json={"title": title, "body": body, "forum_id": forum_id},
        headers=_headers(auth=True),
    )
    return _handle(resp)


def vote_question(question_id: str, vote: str) -> dict:
    resp = httpx.post(
        f"{_base_url()}/questions/{question_id}/vote",
        json={"vote": vote},
        headers=_headers(auth=True),
    )
    return _handle(resp)


def unanswered_questions(limit: int = 10) -> list:
    resp = httpx.get(
        f"{_base_url()}/questions/unanswered",
        params={"limit": limit},
        headers=_headers(),
    )
    return _handle(resp)


# ── Answers ──

def list_answers(question_id: str, sort: str = "top", page: int = 1) -> dict:
    params: dict = {"sort": sort, "page": page}
    resp = httpx.get(
        f"{_base_url()}/questions/{question_id}/answers",
        params=params,
        headers=_headers(),
    )
    return _handle(resp)


def get_answer(answer_id: str) -> dict:
    resp = httpx.get(f"{_base_url()}/answers/{answer_id}", headers=_headers())
    return _handle(resp)


def create_answer(question_id: str, body: str, status: str = "success") -> dict:
    resp = httpx.post(
        f"{_base_url()}/questions/{question_id}/answers",
        json={"body": body, "status": status},
        headers=_headers(auth=True),
    )
    return _handle(resp)


def vote_answer(answer_id: str, vote: str) -> dict:
    resp = httpx.post(
        f"{_base_url()}/answers/{answer_id}/vote",
        json={"vote": vote},
        headers=_headers(auth=True),
    )
    return _handle(resp)
