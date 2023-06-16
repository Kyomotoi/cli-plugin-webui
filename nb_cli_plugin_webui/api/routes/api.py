from fastapi import APIRouter

from nb_cli_plugin_webui.api.routes import (
    log,
    check,
    files,
    driver,
    adapter,
    project,
    performance,
    authentication,
)

router = APIRouter()
router.include_router(authentication.router, tags=["authentication"], prefix="/auth")
router.include_router(performance.router, tags=["performance"], prefix="/performance")
router.include_router(adapter.router, tags=["adapter"], prefix="/adapter")
router.include_router(project.router, tags=["project"], prefix="/project")
router.include_router(driver.router, tags=["driver"], prefix="/driver")
router.include_router(check.router, tags=["check"], prefix="/check")
router.include_router(files.router, tags=["files"], prefix="/files")
router.include_router(log.router, tags=["log"], prefix="/log")
