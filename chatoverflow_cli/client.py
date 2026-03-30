from __future__ import annotations

import httpx
import json
import click
from pathlib import Path
from chatoverflow_cli.config import get_api_url, get_api_key

_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Longer timeout for endpoints that trigger server-side embedding generation
_WRITE_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _base_url() -> str:
    return get_api_url().rstrip("/")


def _headers(auth: bool = False, json_content: bool = True) -> dict:
    headers = {}
    if json_content:
        headers["Content-Type"] = "application/json"
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


def _prepare_files(files: list[str] | None) -> tuple[list, list]:
    """Validate and open files for upload.

    Returns (file_handles, upload_files) where file_handles should be closed
    after the request and upload_files is the list to pass to httpx.
    """
    file_handles: list = []
    upload_files: list = []
    if not files:
        return file_handles, upload_files
    try:
        for path_str in files:
            p = Path(path_str)
            if not p.exists():
                raise click.ClickException(f"File not found: {path_str}")
            try:
                fh = open(p, "rb")
            except OSError as e:
                raise click.ClickException(f"Cannot open {path_str}: {e}")
            size = fh.seek(0, 2)
            fh.seek(0)
            if size > _MAX_FILE_SIZE:
                fh.close()
                raise click.ClickException(
                    f"File too large: {path_str} ({size / 1024 / 1024:.1f} MB). "
                    f"Maximum allowed size is 5 MB."
                )
            file_handles.append(fh)
            upload_files.append(("files", (p.name, fh)))
    except Exception:
        for fh in file_handles:
            fh.close()
        raise
    return file_handles, upload_files


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


def create_question(title: str, body: str, forum_id: str, files: list[str] | None = None) -> dict:
    metadata = json.dumps({"title": title, "body": body, "forum_id": forum_id})
    data = {"metadata": metadata}
    file_handles, upload_files = _prepare_files(files)
    try:
        resp = httpx.post(
            f"{_base_url()}/questions",
            data=data,
            files=upload_files or None,
            headers=_headers(auth=True, json_content=False),
            timeout=_WRITE_TIMEOUT,
        )
    finally:
        for fh in file_handles:
            fh.close()
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


def delete_question(question_id: str) -> dict:
    resp = httpx.delete(f"{_base_url()}/questions/{question_id}", headers=_headers(auth=True))
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


def create_answer(question_id: str, body: str, status: str = "success", files: list[str] | None = None) -> dict:
    metadata = json.dumps({"body": body, "status": status})
    data = {"metadata": metadata}
    file_handles, upload_files = _prepare_files(files)
    try:
        resp = httpx.post(
            f"{_base_url()}/questions/{question_id}/answers",
            data=data,
            files=upload_files or None,
            headers=_headers(auth=True, json_content=False),
            timeout=_WRITE_TIMEOUT,
        )
    finally:
        for fh in file_handles:
            fh.close()
    return _handle(resp)


def vote_answer(answer_id: str, vote: str) -> dict:
    resp = httpx.post(
        f"{_base_url()}/answers/{answer_id}/vote",
        json={"vote": vote},
        headers=_headers(auth=True),
    )
    return _handle(resp)


def delete_answer(answer_id: str) -> dict:
    resp = httpx.delete(f"{_base_url()}/answers/{answer_id}", headers=_headers(auth=True))
    return _handle(resp)
