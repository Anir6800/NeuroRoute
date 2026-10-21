"""Firebase Auth *emulator* ID-token verification. DEV ONLY.

Emulator tokens are unsigned (alg "none"): the Admin SDK does not check signature or expiry
in emulator mode, so anyone can forge them. This module therefore refuses non-loopback
emulator hosts and non-"demo-" project ids (see Settings), and checks `exp` itself.
Never reuse this for a real Firebase project.
"""
import os
import time
from typing import Annotated

import firebase_admin
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from pydantic import BaseModel

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)
_UNAUTH = {"WWW-Authenticate": "Bearer"}
CLOCK_SKEW_S = 10


class AuthUser(BaseModel):
    uid: str
    email: str | None = None
    role: str


def _fail(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail, headers=_UNAUTH if code == 401 else None)


def _app(settings: Settings) -> firebase_admin.App:
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.auth_emulator_host
    try:
        return firebase_admin.get_app("neuroroute")
    except ValueError:
        return firebase_admin.initialize_app(
            options={"projectId": settings.firebase_project_id}, name="neuroroute"
        )


def verify_token(token: str, settings: Settings, now: float | None = None) -> AuthUser:
    """Return the user for a valid emulator ID token or raise HTTPException 401/403."""
    try:
        claims = auth.verify_id_token(token, app=_app(settings))
    except auth.InvalidIdTokenError:
        # Wrong Firebase project (aud) is an authorization problem, anything else is not authenticated.
        try:
            aud = jwt.decode(token, options={"verify_signature": False}).get("aud")
        except jwt.PyJWTError:
            aud = None
        if aud and aud != settings.firebase_project_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "Token is for a different project") from None
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None
    except (ValueError, FirebaseError):  # SDK/config failure: fail closed
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Token could not be verified") from None

    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or exp + CLOCK_SKEW_S < (now if now is not None else time.time()):
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Token expired")
    role = claims.get("role")
    if role not in settings.allowed_roles:
        raise _fail(status.HTTP_403_FORBIDDEN, "Role not permitted")
    return AuthUser(uid=claims["uid"], email=claims.get("email"), role=role)


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthUser:
    if creds is None:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return verify_token(creds.credentials, settings)
