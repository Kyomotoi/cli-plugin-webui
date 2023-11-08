import json
from typing import Any
from pathlib import Path

import click
from nb_cli.cli import CLI_DEFAULT_STYLE
from noneprompt import InputPrompt, ConfirmPrompt
from pydantic import Field, BaseModel, SecretStr, ValidationError

from nb_cli_plugin_webui.i18n import _

from .utils.security import salt
from .utils.storage import get_config_file
from .utils.string_utils import (
    TokenComplexityError,
    check_string_complexity,
    generate_complexity_string,
)

CONFIG_FILE = get_config_file("config.json")


class SecretStrJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, SecretStr):
            return o.get_secret_value()
        return super().default(o)


class AppConfig(BaseModel):
    base_dir: str = Field(str(), description="基础目录，创建实例将由此开始")
    host: str = Field(default="localhost", description="主机名")
    port: str = Field(default="12345", description="端口号")
    debug: bool = Field(default=False, description="是否开启调试模式")
    enable_api_document: bool = Field(default=False, description="是否开启 API 文档")

    log_level: str = Field(default="INFO", description="日志等级")

    secret_key: SecretStr = Field(SecretStr(str()), description="验证密钥的密钥")
    hashed_token: str = Field(str(), description="哈希后的 token")
    salt: SecretStr = Field(SecretStr(str()), description="盐值")

    allowed_origins: list = Field(
        default=["*"],
        description="限定访问来源",
    )

    process_log_destroy_seconds: int = Field(
        default=5 * 60, description="进程单条日志销毁时间（秒）"
    )

    extension_store_visible_items: int = Field(default=12, description="扩展商店每页显示数量")

    def to_json(self) -> str:
        return json.dumps(self.dict(), cls=SecretStrJSONEncoder)

    def check_necessary_config(self) -> bool:
        return bool(
            self.base_dir and self.secret_key and self.hashed_token and self.salt
        )

    def reset_token(self, token: str) -> None:
        self.salt = SecretStr(salt.gen_salt())
        self.hashed_token = salt.get_token_hash(self.salt.get_secret_value() + token)

    @classmethod
    def get_description(cls, field_name: str) -> str:
        return cls.__fields__[field_name].field_info.description


def generate_config():
    click.secho(_("Welcome to use NB CLI WebUI."), fg="green")
    click.secho("")
    click.secho(_("[Token Setting]"), fg="green")
    click.secho(_("Token is your key to access WebUI."))
    if ConfirmPrompt(_("Do you want it generated?")).prompt(style=CLI_DEFAULT_STYLE):
        token = generate_complexity_string(use_digits=True, use_punctuation=True)
    else:
        token = InputPrompt(_("Please enter token:")).prompt(style=CLI_DEFAULT_STYLE)
        while True:
            try:
                check_string_complexity(token)
                break
            except TokenComplexityError as err:
                click.secho(str(err))

            token = InputPrompt(_("Please enter again:")).prompt(
                style=CLI_DEFAULT_STYLE
            )

    click.secho(_("Your token is:"))
    click.secho(f"\n{token}\n", fg="green")
    click.secho(_("ATTENTION, TOKEN ONLY SHOW ONCE."), fg="red", bold=True)

    click.secho("")
    click.secho(_("[Server Setting]"), fg="green")
    host = "localhost"
    port = "12345"
    if ConfirmPrompt(_("Do you want to decide (host) and (port) by yourself?")).prompt(
        style=CLI_DEFAULT_STYLE
    ):
        host = InputPrompt(_("Please enter host:")).prompt(style=CLI_DEFAULT_STYLE)
        port = InputPrompt(_("Please enter port:")).prompt(style=CLI_DEFAULT_STYLE)
        while True:
            try:
                if int(port) < 0 or int(port) > 65535:
                    raise ValueError
                break
            except ValueError:
                click.secho(_("Port must be between 0 and 65535."))
                port = InputPrompt(_("Please enter port:")).prompt(
                    style=CLI_DEFAULT_STYLE
                )

        click.secho(_("Your webui url is:"))
        click.secho(f"http://{host}:{port}/", fg="green")
    else:
        click.secho(_("Your webui url will decide by nb-cli."))

    click.secho("")
    click.secho(_("[General Setting]"), fg="green")
    click.secho(_("- Base directory. Example:"))
    click.secho(("  * Linux: /home/(user)/"))
    click.secho(("  * MacOS: /Users/(user)/"))
    click.secho(("  * Windows: C:/Users/Public/Pictures"))
    click.secho(_("- NoneBot will be stored here."))
    while True:
        base_dir = InputPrompt(_("Please enter base directory:")).prompt(
            style=CLI_DEFAULT_STYLE
        )
        path = Path(base_dir)

        if base_dir and path.is_absolute() and path.is_dir():
            break

        if not base_dir:
            click.secho(_("Directory must not be empty."))
        if not path.exists():
            click.secho(_("Directory does not exist."))
        if not path.is_absolute():
            click.secho(_("Path must be absolute."))
        if not path.is_dir():
            click.secho(_("Path must be folder."))

    click.secho("")
    click.secho(_("[Setting Overview]"), fg="green")
    click.secho(_("Token: {token}").format(token=token))
    click.secho(_("WebUI URL: http://{host}:{port}/").format(host=host, port=port))
    click.secho(_("Base directory: {base_dir}").format(base_dir=base_dir))
    if not ConfirmPrompt(_("Confirm or not:")).prompt(style=CLI_DEFAULT_STYLE):
        click.secho(_("Cleaning..."))
        return

    _salt = salt.gen_salt()
    hashed_token = salt.get_token_hash(_salt + token)

    user_config = AppConfig(
        base_dir=base_dir,
        host=host,
        port=port,
        secret_key=SecretStr(
            generate_complexity_string(32, use_digits=True, use_punctuation=True)
        ),
        salt=SecretStr(_salt),
        hashed_token=hashed_token,
    )
    CONFIG_FILE.write_text(user_config.to_json(), encoding="utf-8")


try:
    Config = AppConfig.parse_file(CONFIG_FILE)
except ValidationError as err:
    click.secho(_("Config file is invalid: {err}").format(err=err), fg="red")
    click.secho(_("Enter command to clear: nb ui clear"), fg="yellow")
    exit(-1)
except FileNotFoundError:
    generate_config()
