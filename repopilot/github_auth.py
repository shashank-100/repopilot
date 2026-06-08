"""GitHub authentication — App installation tokens with PAT fallback.

Resolution order for a usable token:
  1. GitHub App: if GITHUB_APP_ID + GITHUB_PRIVATE_KEY are set, mint a short-lived
     installation access token (Devin-style: the app is installed per-repo and we
     exchange a JWT for an installation token scoped to that install).
  2. PAT: if GITHUB_TOKEN is set, use it directly.
  3. None: callers skip PR creation gracefully.

Installation tokens are cached until ~5 min before expiry.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)

_GH_API = "https://api.github.com"


@dataclass
class _CachedToken:
    token: str
    expires_at: float  # epoch seconds


_install_token_cache: dict[str, _CachedToken] = {}


def _private_key() -> str | None:
    """Return the app private key from env (supports \\n-escaped single-line)."""
    key = os.getenv("GITHUB_PRIVATE_KEY")
    if not key:
        return None
    # Railway/Vercel store multi-line secrets with literal \n — restore them.
    if "\\n" in key and "-----BEGIN" in key:
        key = key.replace("\\n", "\n")
    return key


def _app_jwt() -> str | None:
    """Mint a 10-minute app JWT signed with the app private key."""
    app_id = os.getenv("GITHUB_APP_ID")
    key = _private_key()
    if not app_id or not key:
        return None
    import jwt  # PyJWT

    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": app_id}
    return jwt.encode(payload, key, algorithm="RS256")


def _installation_id_for(owner: str, repo: str, app_jwt: str) -> int | None:
    """Find the installation id covering owner/repo."""
    # Explicit override avoids an API call when the app is single-install.
    env_id = os.getenv("GITHUB_INSTALLATION_ID")
    if env_id:
        return int(env_id)
    resp = httpx.get(
        f"{_GH_API}/repos/{owner}/{repo}/installation",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=20,
    )
    if resp.status_code == 200:
        return int(resp.json()["id"])
    logger.warning("github_auth.no_installation", owner=owner, repo=repo, status=resp.status_code)
    return None


def _installation_token(owner: str, repo: str) -> str | None:
    """Mint (and cache) an installation access token for owner/repo."""
    app_jwt = _app_jwt()
    if not app_jwt:
        return None

    cache_key = f"{owner}/{repo}"
    cached = _install_token_cache.get(cache_key)
    if cached and cached.expires_at - 300 > time.time():
        return cached.token

    install_id = _installation_id_for(owner, repo, app_jwt)
    if install_id is None:
        return None

    resp = httpx.post(
        f"{_GH_API}/app/installations/{install_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=20,
    )
    if resp.status_code != 201:
        logger.warning("github_auth.token_failed", status=resp.status_code, body=resp.text[:200])
        return None

    data = resp.json()
    # expires_at like "2024-01-01T00:00:00Z"
    from datetime import datetime, timezone
    exp = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    _install_token_cache[cache_key] = _CachedToken(
        token=data["token"], expires_at=exp.replace(tzinfo=timezone.utc).timestamp()
    )
    logger.info("github_auth.installation_token", owner=owner, repo=repo)
    return data["token"]


def get_token(owner: str, repo: str) -> str | None:
    """Return a usable GitHub token for owner/repo: App install token, else PAT."""
    token = _installation_token(owner, repo)
    if token:
        return token
    pat = os.getenv("GITHUB_TOKEN")
    if pat:
        logger.info("github_auth.using_pat")
        return pat
    return None


def list_accessible_repos() -> list[dict[str, str]]:
    """List repos the GitHub App is installed on (or the PAT can see).

    Returns a list of {full_name, default_branch, private} dicts. Empty if no
    credentials are configured.
    """
    app_jwt = _app_jwt()
    repos: list[dict[str, str]] = []

    if app_jwt:
        # Enumerate installations → mint token → list its repos
        r = httpx.get(
            f"{_GH_API}/app/installations",
            headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
            timeout=20,
        )
        if r.status_code == 200:
            for inst in r.json():
                tr = httpx.post(
                    f"{_GH_API}/app/installations/{inst['id']}/access_tokens",
                    headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
                    timeout=20,
                )
                if tr.status_code != 201:
                    continue
                tok = tr.json()["token"]
                page = 1
                while True:
                    rr = httpx.get(
                        f"{_GH_API}/installation/repositories?per_page=100&page={page}",
                        headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                        timeout=20,
                    )
                    if rr.status_code != 200:
                        break
                    batch = rr.json().get("repositories", [])
                    for x in batch:
                        repos.append({
                            "full_name": x["full_name"],
                            "default_branch": x.get("default_branch", "main"),
                            "private": x.get("private", False),
                        })
                    if len(batch) < 100:
                        break
                    page += 1
        return repos

    # PAT fallback
    pat = os.getenv("GITHUB_TOKEN")
    if pat:
        rr = httpx.get(
            f"{_GH_API}/user/repos?per_page=100&sort=updated",
            headers={"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"},
            timeout=20,
        )
        if rr.status_code == 200:
            for x in rr.json():
                repos.append({
                    "full_name": x["full_name"],
                    "default_branch": x.get("default_branch", "main"),
                    "private": x.get("private", False),
                })
    return repos
