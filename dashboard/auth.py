"""
AlphaHound Dashboard — access gate.

Single shared access code (internal use). Validates the code server-side,
issues a signed, expiring session cookie, and protects all routes except
the login page, the login API, and static assets.

Wire-up in api.py (after `app = FastAPI(...)`):

    from dashboard.auth import install_auth
    install_auth(app)

Config (.env):
    DASHBOARD_ACCESS_CODE    access code; defaults to 6649 if unset
    DASHBOARD_SESSION_SECRET signing secret; defaults to a built-in if unset
    DASHBOARD_SESSION_HOURS  cookie lifetime, default 168 (7 days)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

log = logging.getLogger("alphahound.dashboard.auth")

COOKIE_NAME = "ah_session"
LOGIN_PAGE  = r"C:\alphahound_project\dashboard\login.html"

# Hardcoded default access code (overridable via DASHBOARD_ACCESS_CODE in .env).
DEFAULT_CODE   = "6649"
# Hardcoded fallback signing secret so the gate works without any .env entry.
# Rotate by setting DASHBOARD_SESSION_SECRET in .env (invalidates existing sessions).
DEFAULT_SECRET = "ah-dash-3f9c1e7a2b8d4655-2026"

# Paths that never require auth.
_PUBLIC_PREFIXES = ("/static/", "/login", "/api/login", "/favicon")


def _cfg():
    code   = os.environ.get("DASHBOARD_ACCESS_CODE", DEFAULT_CODE).strip() or DEFAULT_CODE
    secret = os.environ.get("DASHBOARD_SESSION_SECRET", DEFAULT_SECRET).strip() or DEFAULT_SECRET
    hours  = int(os.environ.get("DASHBOARD_SESSION_HOURS", "168"))
    return code, secret, hours


def _sign(expires_at: int, secret: str) -> str:
    """Token = expiry.hexsig — opaque, tamper-evident, self-expiring."""
    msg = str(expires_at).encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"{expires_at}.{sig}"


def _valid(token: str, secret: str) -> bool:
    if not token or "." not in token:
        return False
    try:
        exp_str, sig = token.split(".", 1)
        expires_at = int(exp_str)
    except (ValueError, TypeError):
        return False
    if expires_at < int(time.time()):
        return False  # expired
    expected = hmac.new(secret.encode(), exp_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def install_auth(app: FastAPI) -> None:
    code, secret, hours = _cfg()

    @app.post("/api/login")
    async def login(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        supplied = (body.get("code") or "").strip()
        # constant-time compare to avoid leaking length/timing
        if not hmac.compare_digest(supplied, code):
            return JSONResponse({"ok": False, "error": "Invalid access code"}, status_code=401)

        expires_at = int(time.time()) + hours * 3600
        token = _sign(expires_at, secret)
        resp = JSONResponse({"ok": True})
        resp.set_cookie(
            COOKIE_NAME, token,
            max_age=hours * 3600,
            httponly=True,
            samesite="lax",
            # secure=True,  # enable if/when the dashboard is served over HTTPS
        )
        return resp

    @app.post("/api/logout")
    async def logout():
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE_NAME)
        return resp

    @app.get("/login")
    def login_page():
        return FileResponse(LOGIN_PAGE)

    @app.middleware("http")
    async def gate(request: Request, call_next):
        path = request.url.path
        if any(path == p or path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME, "")
        if _valid(token, secret):
            return await call_next(request)

        # Not authenticated. API calls get 401 JSON; page loads redirect to /login.
        if path.startswith("/api/"):
            return JSONResponse({"error": "unauthorized", "login": "/login"}, status_code=401)
        return RedirectResponse(url="/login", status_code=302)

    log.info("DASHBOARD gate ENABLED — access code required (session %dh).", hours)
