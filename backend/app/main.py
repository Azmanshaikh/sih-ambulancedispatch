from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import engine, Base
from app.api import accounts, ai, hospitals, tracking
from app.services.fleet import init_fleet, tick_fleet
import asyncio
import contextlib

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_fleet()

    async def fleet_loop():
        try:
            while True:
                tick_fleet()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            return

    tracker = asyncio.create_task(fleet_loop())
    try:
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
    await engine.dispose()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tracking.router)
app.include_router(ai.router)
app.include_router(hospitals.router)
app.include_router(accounts.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
