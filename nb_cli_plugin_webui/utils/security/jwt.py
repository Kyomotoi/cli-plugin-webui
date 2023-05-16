from typing import Dict
from datetime import datetime, timedelta

import jwt
from pydantic import ValidationError

from nb_cli_plugin_webui.i18n import _
from nb_cli_plugin_webui.models.schemas.jwt import JWTMeta, JWTUser

JWT_SUBJECT: str = "access"
ALGORITHM: str = "HS256"
EXPIRE_SECONDS: int = 60 * 60 * 24


def create_jwt(
    payload: Dict[str, str], secret_key: str, expire_seconds: timedelta
) -> str:
    to_encode = payload.copy()
    expire = datetime.utcnow() + expire_seconds
    to_encode.update(JWTMeta(exp=expire, sub=JWT_SUBJECT).dict())
    return jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)


def create_access_for_cookie(cookie: str, secret_key: str) -> str:
    return create_jwt(
        payload=JWTUser(cookie=cookie).dict(),
        secret_key=secret_key,
        expire_seconds=timedelta(EXPIRE_SECONDS),
    )


def get_cookie_from_access(cookie: str, secret_key: str) -> str:
    ...


def verify_and_read_jwt(cookie: str, secret_key: str) -> str:
    try:
        return JWTUser(**jwt.decode(cookie, secret_key, algorithms=[ALGORITHM])).cookie
    except jwt.ExpiredSignatureError as err:
        raise ValueError(_("Session(cookie) has expired.")) from err
    except jwt.InvalidTokenError as err:
        raise ValueError(_("Invalid JWT.")) from err
    except ValidationError as err:
        raise ValueError(_("Malformed payload in cookie.")) from err