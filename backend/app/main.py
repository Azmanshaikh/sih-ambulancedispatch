from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import engine, Base
from app.api import ai, auth, hospitals, tracking
import contextlib

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up on shutdown
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

app.include_router(auth.router)
app.include_router(tracking.router)
app.include_router(ai.router)
app.include_router(hospitals.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
