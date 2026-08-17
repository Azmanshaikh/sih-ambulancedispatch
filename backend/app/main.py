from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import engine, Base
from app.api import accounts, ai, hospitals, tracking
from app.services.fleet import init_fleet, tick_fleet
from app.services.runtime_state import apply_fleet_events, save_mission
from app.services.corridor import tick_corridor_alerts
import asyncio
import contextlib

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_fleet()

    async def finish_if_needed(mission: dict):
        if not mission or mission.get("phase") != "complete" or mission.get("report"):
            return
        from app.services.patient_care import generate_trip_report

        report = await generate_trip_report(mission)
        mission["report"] = report
        save_mission(mission)

    async def fleet_loop():
        try:
            while True:
                events = tick_fleet()
                changed_list = apply_fleet_events(events)
                for changed in changed_list:
                    if changed.get("phase") == "complete" and not changed.get("report"):
                        asyncio.create_task(finish_if_needed(changed))
                tick_corridor_alerts()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            return

    tracker = asyncio.create_task(fleet_loop())
    try:
        if engine is not None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # DB is optional for map/dispatch; keep the API up if Postgres is down.
        pass
    yield
    tracker.cancel()
    try:
        await tracker
    except asyncio.CancelledError:
        pass
    if engine is not None:
        await engine.dispose()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

_cors = [o.strip() for o in (settings.CORS_ORIGINS or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["*"],
    allow_credentials=bool(_cors),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tracking.router)
app.include_router(ai.router)
app.include_router(hospitals.router)
app.include_router(accounts.router)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "JEEVAN API",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}
