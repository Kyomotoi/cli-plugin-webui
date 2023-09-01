import os
import sys
import json
import shutil
import asyncio
from pathlib import Path
from typing import Dict, List

from nb_cli.config import ConfigManager
from nb_cli.handlers.venv import create_virtualenv
from nb_cli.handlers.meta import get_default_python
from nb_cli.config import SimpleInfo as CliSimpleInfo
from nb_cli.cli.commands.project import ProjectContext
from fastapi import Body, APIRouter, HTTPException, status
from nb_cli.handlers.project import create_project, generate_run_script

from nb_cli_plugin_webui.api.dependencies.files import BASE_DIR
from nb_cli_plugin_webui.models.schemas.store import SimpleInfo
from nb_cli_plugin_webui.utils import generate_complexity_string
from nb_cli_plugin_webui.exceptions import NonebotProjectIsNotExist
from nb_cli_plugin_webui.api.dependencies.pip import call_pip_install
from nb_cli_plugin_webui.models.domain.process import LogLevel, CustomLog
from nb_cli_plugin_webui.api.dependencies.project import NonebotProjectManager
from nb_cli_plugin_webui.api.dependencies.process.manager import ProcessManager
from nb_cli_plugin_webui.api.dependencies.process.process import CustomProcessor
from nb_cli_plugin_webui.api.dependencies.process.log import (
    LoggerStorage,
    LoggerStorageFather,
)
from nb_cli_plugin_webui.models.schemas.project import (
    CreateProjectData,
    NonebotProjectMeta,
    ProjectListResponse,
    CreateProjectResponse,
    DeleteProjectResponse,
)

router = APIRouter()


@router.post("/create", response_model=CreateProjectResponse)
async def create_nonebot_project(
    project_data: CreateProjectData = Body(embed=True),
) -> CreateProjectResponse:
    project_name = project_data.project_name.replace(" ", "-")

    context = ProjectContext()
    context.variables["project_name"] = project_name
    context.variables["drivers"] = json.dumps(
        {driver.project_link: driver.dict() for driver in project_data.drivers}
    )
    context.packages.extend([driver.project_link for driver in project_data.drivers])

    context.variables["adapters"] = json.dumps(
        {adapter.project_link: adapter.dict() for adapter in project_data.adapters}
    )
    context.packages.extend([adapter.project_link for adapter in project_data.adapters])

    if not project_data.is_bootstrap:
        context.variables["use_src"] = project_data.use_src

    base_project_dir = BASE_DIR / Path(project_data.project_dir)
    project_dir = base_project_dir / project_name

    log = LoggerStorage()
    log_key = generate_complexity_string(8)
    LoggerStorageFather.add_storage(log, log_key)

    async def notice(log: LoggerStorage):
        async def _err_parse(err: Exception):
            log_model = CustomLog(level=LogLevel.ERROR, message=str(err))
            await log.add_log(log_model)

            try:
                shutil.rmtree(project_dir)
            except OSError:
                return

            log_model = CustomLog(message="All files about project have been cleared.")
            await log.add_log(log_model)

            log_model = CustomLog(message="❗ Failed...")
            await log.add_log(log_model)

        # Time for frontend ready
        await asyncio.sleep(1)

        log_model = CustomLog(message="Processing at 3s...")
        await log.add_log(log_model)

        await asyncio.sleep(3)

        log_model = CustomLog(message=f"Project name: {project_data.project_name}")
        await log.add_log(log_model)

        log_model = CustomLog(message=f"Project Dir: {project_dir.absolute()}")
        await log.add_log(log_model)

        drivers = [driver.project_link for driver in project_data.drivers]
        log_model = CustomLog(message=f"Project Driver: {', '.join(drivers)}")
        await log.add_log(log_model)

        adapters = [adapter.project_link for adapter in project_data.adapters]
        log_model = CustomLog(message=f"Project Adapter: {', '.join(adapters)}")
        await log.add_log(log_model)

        log_model = CustomLog(message=str())
        await log.add_log(log_model)

        try:
            log_model = CustomLog(message="Generate NoneBot project files...")
            await log.add_log(log_model)

            create_project(
                "bootstrap" if project_data.is_bootstrap else "simple",
                {"nonebot": context.variables},
                str(base_project_dir.absolute()),
            )

            log_model = CustomLog(message="Finished generate NoneBot project files")
            await log.add_log(log_model)
        except Exception as err:
            await _err_parse(err)
            return

        try:
            log_model = CustomLog(message="Initialization dependencies...")
            await log.add_log(log_model)

            venv_dir = project_dir / ".venv"
            await create_virtualenv(venv_dir, prompt=project_name, python_path=None)
        except Exception as err:
            await _err_parse(err)
            return

        config_manager = ConfigManager(working_dir=project_dir, use_venv=True)

        try:
            log_model = CustomLog(message="Installing dependencies...")
            await log.add_log(log_model)

            proc, log = await call_pip_install(
                ["nonebot2", *context.packages],
                ["-i", project_data.mirror_url],
                log_storage=log,
                python_path=config_manager.python_path,
            )
            await proc.wait()
        except Exception as err:
            await _err_parse(err)
            return

        _adapters: List[SimpleInfo] = [
            SimpleInfo.parse_obj(adapter.dict()) for adapter in project_data.adapters
        ]
        _drivers: List[SimpleInfo] = [
            SimpleInfo.parse_obj(driver.dict()) for driver in project_data.drivers
        ]

        project_id = generate_complexity_string(6)
        manager = NonebotProjectManager(project_id)
        manager.add(
            project_name=project_name,
            project_dir=project_dir,
            mirror_url=project_data.mirror_url,
            adapters=_adapters,
            drivers=_drivers,
        )

        manager.write_to_env(".env", "ENVIRONMENT", "prod")

        log_model = CustomLog(message="✨ Done!")
        await log.add_log(log_model)

    asyncio.create_task(notice(log))
    asyncio.get_running_loop().call_later(
        600, LoggerStorageFather.storages.pop, log_key
    )

    return CreateProjectResponse(log_key=log_key)


@router.delete("/delete", response_model=DeleteProjectResponse)
async def delete_nonebot_project(project_id: str) -> DeleteProjectResponse:
    manager = NonebotProjectManager(project_id)
    data = manager.read()

    try:
        shutil.rmtree(data.project_dir)
    except OSError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"删除实例失败 {err=}"
        )

    manager.remove()

    return DeleteProjectResponse(project_id=project_id)


@router.get("/list", response_model=ProjectListResponse)
async def get_nonebot_projects() -> ProjectListResponse:
    try:
        projects = NonebotProjectManager.get_projects()
    except Exception:
        projects = dict()

    if not projects:
        return ProjectListResponse(projects=projects)

    processes = ProcessManager.processes

    new_data: Dict[str, NonebotProjectMeta] = dict()
    for project_id in projects:
        project = projects[project_id]

        for process_id in processes:
            process = processes[process_id]
            if project.project_id == process_id and process.process_is_running:
                is_running = True
                break
        else:
            is_running = False

        project.is_running = is_running
        new_data[project.project_id] = project

    return ProjectListResponse(projects=new_data)


@router.post("/run")
async def run_nonebot_project(project_id: str = Body(embed=True)) -> None:
    project = NonebotProjectManager(project_id)
    try:
        project.read()
    except NonebotProjectIsNotExist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"实例 {project_id=} 不存在"
        )

    project_details = project.read()
    project_dir = Path(project_details.project_dir)

    env = os.environ.copy()
    env["TERM"] = "xterm-color"
    if sys.platform == "win32":
        venv_path = project_dir / Path(".venv\\Scripts")
        env["PATH"] = f"{venv_path.absolute()};" + env["PATH"]
    else:
        venv_path = project_dir / Path(".venv\\bin")
        env["PATH"] = f"{venv_path.absolute()}:" + env["PATH"]

    run_script_file = project_dir / "bot.py"

    process = ProcessManager.get_process(project_id)
    if process:
        if process.process_is_running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"实例 {project_id=} 正在运行中",
            )
        else:
            await process.start()
    else:
        python_path = project.config_manager.python_path
        if python_path is None:
            python_path = await get_default_python()

        if run_script_file.is_file():
            process = CustomProcessor(
                python_path,
                run_script_file,
                cwd=project_dir,
                env=env,
                log_rotation_time=5 * 60,
            )
        else:
            raw_adapters = project_details.adapters
            new_adapters: List[CliSimpleInfo] = list()
            for adapter in raw_adapters:
                new_adapters.append(
                    CliSimpleInfo(name=adapter.name, module_name=adapter.module_name)
                )

            run_script = await generate_run_script(
                adapters=new_adapters,
                builtin_plugins=project_details.builtin_plugins,
            )

            process = CustomProcessor(
                python_path,
                "-c",
                run_script,
                cwd=project_dir,
                env=env,
                log_rotation_time=5 * 60,
            )

        log = process.get_log_record()
        LoggerStorageFather.add_storage(log, project_id)
        ProcessManager.add_process(process, project_id)
        await process.start()


@router.post("/stop")
async def stop_nonebot_project(project_id: str = Body(embed=True)):
    process = ProcessManager.get_process(project_id)
    if process is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无法找到对应的实例进程"
        )

    await process.stop()

    return {"detail": "OK"}


@router.post("/write")
async def write_nonebot_project_process(
    project_id: str = Body(embed=True), content: str = Body(embed=True)
):
    process = ProcessManager.get_process(project_id)
    if process is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="无法找到对应的实例进程"
        )

    result = None
    if process.process_is_running:
        content = content + os.linesep
        try:
            result = await process.write_stdin(content.encode())
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"写入进程失败 {err=}"
            )
    else:
        process.args = (content,)
        await process.start()

    return {"detail": result}