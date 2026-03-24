from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_agent_manager
from app.api.routes import router
from app.core.config import get_settings
from app.ui.admin import router as admin_router

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup() -> None:
    get_agent_manager().start_background_tasks()


@app.on_event("shutdown")
async def shutdown() -> None:
    await get_agent_manager().stop_background_tasks()
