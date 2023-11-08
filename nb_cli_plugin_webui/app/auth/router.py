from fastapi import APIRouter, HTTPException, status

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.utils.security import jwt, salt

from .schemas import LoginRequest

router = APIRouter()


@router.post("/login", response_model=GenericResponse[str])
async def auth_token(data: LoginRequest) -> GenericResponse[str]:
    """
    - 登录, 成功后返回 JWT 密钥
    """
    if not salt.verify_token(
        Config.salt.get_secret_value() + data.token,
        Config.hashed_token,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="密钥不可用")

    secret_key = Config.secret_key.get_secret_value()
    jwt_token = jwt.create_access_for_header(data.mark, secret_key)
    return GenericResponse(detail=jwt_token)
