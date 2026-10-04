"""Same-origin HTTP API hosted by Reflex through its public api_transformer hook."""

import json
import logging
import os
import secrets
import sqlite3

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..db_handler import Database
from .application import ApplicationService
from .auth import SESSION_SECONDS, PasswordAuth, Sessions
from .errors import AppError
from .validation import text
from .services import RequestContext, SQLiteFrontendService

COOKIE = "intersect_session"
CSRF_COOKIE = "intersect_csrf"
log = logging.getLogger(__name__)


def create_api(database=None, authentication=None, embedding_generator=None):
    database = database or Database()
    service = ApplicationService(database, embedding_generator)
    frontend = SQLiteFrontendService(database, embedding_generator)
    # Defer expensive adapter construction until the first account operation.
    adapter = authentication
    sessions = Sessions(database)
    origins = [
        value.strip().rstrip("/")
        for value in os.getenv("INTERSECT_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    ]
    secure = os.getenv("INTERSECT_SECURE_COOKIES", "").lower() in ("1", "true")

    def cookie(response, key, value, request, max_age=SESSION_SECONDS):
        is_secure = secure or request.url.scheme == "https"
        response.set_cookie(
            key,
            value,
            max_age=max_age,
            httponly=True,
            secure=is_secure,
            samesite="none" if is_secure else "lax",
            path="/",
        )

    async def owner(request):
        return await run_in_threadpool(sessions.resolve, request.cookies.get(COOKIE))

    async def payload(request):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if origin not in [expected, *origins]:
            raise AppError("This request came from an unrecognized origin.", 403)
        csrf = request.headers.get("x-csrf-token", "")
        saved = request.cookies.get(CSRF_COOKIE, "")
        if not csrf or not saved or not secrets.compare_digest(csrf, saved):
            raise AppError("Please refresh this page before submitting again.", 403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise AppError("A JSON request is required.", 415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise AppError("This request is too large.", 413)
        import json

        try:
            value = json.loads(body)
        except (ValueError, UnicodeError):
            raise AppError("Invalid JSON request.") from None
        if not isinstance(value, dict):
            raise AppError("Invalid request.")
        return value

    async def endpoint(request: Request):
        nonlocal adapter
        path = request.url.path.rstrip("/").split("/api/")[-1]
        try:
            if path == "session":
                csrf = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
                try:
                    current = await owner(request)
                except AppError as error:
                    if error.status != 401:
                        raise
                    current = None
                response = JSONResponse({"profile": current, "csrfToken": csrf})
                cookie(response, CSRF_COOKIE, csrf, request)
            elif path == "moderate-message":
                # Local sample accounts have no authenticated identity. Check
                # their messages with the same policy without saving content.
                value = await payload(request)
                await run_in_threadpool(text, value.get("text"), "Message", 1000)
                response = JSONResponse({"ok": True})
            elif path in ("login", "register"):
                value = await payload(request)
                if adapter is None:
                    adapter = await run_in_threadpool(PasswordAuth, database)
                current = await run_in_threadpool(getattr(adapter, path), value)
                # Rotate sessions at authentication; invalidate an earlier account.
                await run_in_threadpool(sessions.revoke, request.cookies.get(COOKIE))
                token = await run_in_threadpool(sessions.create, current["id"])
                csrf = secrets.token_urlsafe(32)
                response = JSONResponse({"profile": current, "csrfToken": csrf})
                cookie(response, COOKIE, token, request)
                cookie(response, CSRF_COOKIE, csrf, request)
            else:
                current = await owner(request)
                context = RequestContext(actor_id=current["id"])
                uid = context.actor_id
                if path == "load":
                    value = await frontend.load(
                        context,
                        after_messages=request.query_params.get("afterMessages"),
                    )
                elif path == "messages":
                    value = await run_in_threadpool(
                        service.messages,
                        uid,
                        request.query_params.get("connectionId"),
                        request.query_params.get("before"),
                    )
                elif path == "admin":
                    value = await run_in_threadpool(service.admin_load, uid)
                elif path == "matching/profile":
                    value = await run_in_threadpool(service.matching.profile, uid)
                elif path == "matches":
                    try:
                        raw_trait = request.query_params.get("trait")
                        if raw_trait and len(raw_trait) > 1024:
                            raise ValueError
                        trait = json.loads(raw_trait) if raw_trait else None
                        limit = int(request.query_params.get("limit", "20"))
                    except (ValueError, TypeError):
                        raise AppError("Choose valid matching options.") from None
                    value = await run_in_threadpool(
                        service.matching.candidates,
                        uid,
                        mode=request.query_params.get("mode", "similar"),
                        trait=trait,
                        limit=limit,
                    )
                else:
                    p = await payload(request)
                    if path == "logout":
                        await run_in_threadpool(
                            sessions.revoke, request.cookies.get(COOKIE)
                        )
                        response = JSONResponse({"ok": True})
                        response.delete_cookie(COOKIE, path="/")
                        response.delete_cookie(CSRF_COOKIE, path="/")
                        response.headers["Cache-Control"] = "no-store"
                        return response
                    if path == "admin/action":
                        value = await run_in_threadpool(
                            service.admin_action,
                            uid,
                            p.get("method"),
                            p.get("input", {}),
                        )
                    else:
                        value = await frontend.dispatch(
                            context, p.get("method"), p.get("input", {})
                        )
                response = JSONResponse(value)
        except AppError as error:
            response = JSONResponse(
                {"message": error.message}, status_code=error.status
            )
        except sqlite3.IntegrityError:
            response = JSONResponse(
                {
                    "message": "This record conflicts with an existing record. Refresh and try again."
                },
                status_code=409,
            )
        except Exception:
            log.exception("API request failed: %s", path)
            response = JSONResponse(
                {"message": "The request could not be completed. Please try again."},
                status_code=500,
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    routes = [
        Route("/api/" + path, endpoint, methods=methods)
        for path, methods in (
            ("session", ["GET"]),
            ("moderate-message", ["POST"]),
            ("login", ["POST"]),
            ("register", ["POST"]),
            ("logout", ["POST"]),
            ("load", ["GET"]),
            ("messages", ["GET"]),
            ("action", ["POST"]),
            ("admin", ["GET"]),
            ("matching/profile", ["GET"]),
            ("matches", ["GET"]),
            ("admin/action", ["POST"]),
        )
    ]
    api = Starlette(routes=routes)
    if origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )
    return api
