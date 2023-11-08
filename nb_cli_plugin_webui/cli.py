import os
import webbrowser
from typing import List, cast

import click
from nb_cli.i18n import _ as nb_cli_i18n
from nb_cli.cli import CLI_DEFAULT_STYLE, ClickAliasedGroup, run_sync, run_async
from noneprompt import Choice, ListPrompt, InputPrompt, ConfirmPrompt, CancelledError

from nb_cli_plugin_webui.i18n import _
from nb_cli_plugin_webui.app.config import CONFIG_FILE, Config
from nb_cli_plugin_webui.app.utils.storage import get_data_file
from nb_cli_plugin_webui.app.utils.string_utils import (
    check_string_complexity,
    generate_complexity_string,
)


@click.group(
    cls=ClickAliasedGroup, invoke_without_command=True, help=_("Start up NB CLI UI.")
)
@click.pass_context
@run_async
async def webui(ctx: click.Context):
    if ctx.invoked_subcommand is not None:
        return

    command = cast(ClickAliasedGroup, ctx.command)

    choices: List[Choice[click.Command]] = list()
    for sub_cmd_name in await run_sync(command.list_commands)(ctx):
        if sub_cmd := await run_sync(command.get_command)(ctx, sub_cmd_name):
            choices.append(
                Choice(
                    sub_cmd.help
                    or nb_cli_i18n("Run subcommand {sub_cmd.name!r}").format(
                        sub_cmd=sub_cmd
                    ),
                    sub_cmd,
                )
            )

    try:
        result = await ListPrompt(
            nb_cli_i18n("What do you want to do?"), choices=choices
        ).prompt_async(style=CLI_DEFAULT_STYLE)
    except CancelledError:
        ctx.exit()

    sub_cmd = result.data
    await run_sync(ctx.invoke)(sub_cmd)


@webui.command(help=_("Run NB CLI UI."))
@click.option(
    "-h",
    "--host",
    type=str,
    show_default=True,
    help=_("The host required to access NB CLI UI."),
    default=None,
)
@click.option(
    "-p",
    "--port",
    type=int,
    show_default=True,
    help=_("The port required to access NB CLI UI."),
    default=None,
)
@run_async
async def run(host: str, port: int):
    from . import server

    if not host:
        host = Config.host
    if not port:
        port = int(Config.port)
    else:
        if port < 0 or port > 65535:
            click.secho(_("Port must be between 0 and 65535."))
            return

    try:
        webbrowser.open(f"http://{host}:{port}/")
    except webbrowser.Error:
        pass
    await server.run_server(host, port)


@webui.command(help=_("Reset access token."))
@run_async
async def setting_token():
    if await ConfirmPrompt(_("Do you want it generated?")).prompt_async(
        style=CLI_DEFAULT_STYLE
    ):
        token = generate_complexity_string(use_digits=True, use_punctuation=True)
    else:
        token = await InputPrompt(_("Please enter token:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )
        while True:
            try:
                check_string_complexity(token)
                break
            except Exception as err:
                click.secho(str(err))

            token = await InputPrompt(_("Please enter again:")).prompt_async(
                style=CLI_DEFAULT_STYLE
            )

    click.secho(_("Your token is:"))
    click.secho(f"\n{token}\n", fg="green")
    click.secho(_("ATTENTION, TOKEN ONLY SHOW ONCE."), fg="red", bold=True)

    Config.reset_token(token)
    CONFIG_FILE.write_text(Config.to_json())


CONFIG_DISABLED_LIST = ["hashed_token", "salt", "secret_key"]


@webui.command(help=_("List webui config."))
@run_async
async def list_config():
    for key, value in Config.dict().items():
        if key in CONFIG_DISABLED_LIST:
            continue
        if key == "server":
            for k, v in value.items():
                click.secho(f"{k}: {v}")
            continue
        click.secho(f"{key}: {value}")


@webui.command(help=_("Setting webui config."))
@click.option(
    "-i",
    "--item",
    type=str,
    help=_("The key of config."),
)
@click.option(
    "-s",
    "--setting",
    type=str,
    help=_("The value of config."),
)
@run_async
async def setting_config(item: str, setting: str):
    if not item:
        item = await InputPrompt(_("Please enter key:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )
    if item in CONFIG_DISABLED_LIST:
        click.secho(_("This config is disabled."))
        return
    if not setting:
        setting = await InputPrompt(_("Please enter value:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )

    conf = Config
    config_list = list()
    for key, value in conf.dict().items():
        if key in CONFIG_DISABLED_LIST:
            continue
        if key == "server":
            for k, v in value.items():
                config_list.append(k)
            continue
        config_list.append(key)

    if item not in config_list:
        click.secho(_("This config is not exist."))
        return

    if item == "debug":
        setattr(conf, item, setting.lower() in ["true", "True"])

    setattr(conf, item, setting)
    CONFIG_FILE.write_text(conf.to_json())


@webui.command(help=_("Clear WebUI data. (config, all project info)"))
@run_async
async def clear():
    if await ConfirmPrompt(_("Do you want to clear all data?")).prompt_async(
        style=CLI_DEFAULT_STYLE
    ):
        os.remove(CONFIG_FILE)
        click.secho(_("Clear config file success."))

        try:
            project_info_path = get_data_file("projects.json")
        except FileNotFoundError:
            return
        os.remove(project_info_path)
        click.secho(_("Clear project info file success."))
