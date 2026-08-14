from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from secrets import token_urlsafe

from fastapi import Depends, HTTPException, Request, Response, status

from . import db
from .secrets import admin_token, keyed_fingerprint

SESSION_COOKIE = "quotahub_admin_session"
CSRF_COOKIE = "quotahub_csrf"
SESSION_TTL = timedelta(hours=24)
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_MAX_FAILURES = 5

def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cookie_secure() -> bool:
    return os.environ.get("QUOTAHUB_COOKIE_SECURE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _client_fingerprint(request: Request) -> str:
    source = request.client.host if request.client else "unknown"
    return keyed_fingerprint("admin-login-source", source)


@dataclass(frozen=True)
class LoginAttemptDecision:
    allowed: bool
    failure_count: int
    source_hmac: str


def apply_login_attempt(request: Request, *, success: bool) -> LoginAttemptDecision:
    now = _now()
    source_hmac = _client_fingerprint(request)
    allowed, failure_count = db.apply_admin_login_attempt(
        source_hmac,
        success=success,
        cutoff_iso=_iso(now - LOGIN_WINDOW),
        attempted_at=_iso(now),
        max_failures=LOGIN_MAX_FAILURES,
    )
    return LoginAttemptDecision(
        allowed=allowed,
        failure_count=failure_count,
        source_hmac=source_hmac,
    )


def client_fingerprint(request: Request) -> str:
    return _client_fingerprint(request)


def verify_admin_token(candidate: str) -> bool:
    return compare_digest(candidate.encode("utf-8"), admin_token().encode("utf-8"))


def create_session(response: Response) -> str:
    raw_token = token_urlsafe(32)
    csrf_token = token_urlsafe(32)
    expires_at = _now() + SESSION_TTL
    db.create_admin_session(_token_hash(raw_token), _iso(expires_at))
    secure = cookie_secure()
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    return csrf_token


def clear_session_cookies(response: Response) -> None:
    secure = cookie_secure()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="strict")


def require_admin(request: Request) -> str:
    raw_token = request.cookies.get(SESSION_COOKIE, "")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要管理员登录")
    token_hash = _token_hash(raw_token)
    session = db.get_admin_session(token_hash)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员会话无效")
    if _parse_iso(session.expires_at) <= _now():
        db.delete_admin_session(token_hash)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员会话已过期")
    db.touch_admin_session(token_hash)
    return token_hash


def require_csrf(
    request: Request,
    _session_hash: str = Depends(require_admin),
) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not header_token or not compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")


def delete_session(token_hash: str) -> None:
    db.delete_admin_session(token_hash)
