"""
Monitor Backend — Standalone FastAPI server.

Runs independently from the main POC on its own port (default 8001).
Reads evaluation data from the same SQLite databases the POC writes to.
Has its own monitor_events and monitor_daily_summaries tables.

Launch:
    cd backend && python -m uvicorn monitor_main:app --port 8001 --reload
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Database Setup ─────────────────────────────────────────────────────────

# The monitor connects to the SAME database as the main POC.
# We import the engine from the main POC's compliance database
# (which is the primary one used for unified tables).

def _get_db_engine():
    """Get or create the database engine pointing to the POC's database."""
    # Look for the main database file
    backend_dir = Path(__file__).resolve().parent

    # The main POC uses the compliance/banking database.py modules which
    # create engines from their config. We'll create our own engine pointing
    # to the same file.
    db_path = backend_dir / "document_quality.db"
    if not db_path.exists():
        # Try data subdirectories
        for ws in ["compliance", "banking"]:
            candidate = backend_dir / "data" / ws / "document_quality.db"
            if candidate.exists():
                db_path = candidate
                break

    db_url = f"sqlite:///{db_path.as_posix()}"
    logger.info("Monitor DB: %s", db_url)

    from sqlalchemy import create_engine
    return create_engine(db_url, connect_args={"check_same_thread": False}, echo=False)


def _init_monitor_tables(engine):
    """Create monitor-specific tables if they don't exist."""
    from core.database import Base
    # Import monitor models to register them with Base.metadata
    import core.models.monitor_models  # noqa: F401
    import core.models.db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Monitor tables initialized.")


# ─── App Lifecycle ──────────────────────────────────────────────────────────

engine = None
SessionLocal = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, run aggregation."""
    global engine, SessionLocal

    from sqlalchemy.orm import sessionmaker

    engine = _get_db_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    _init_monitor_tables(engine)

    # Run initial aggregation
    try:
        from core.services.aggregation_service import AggregationService
        agg = AggregationService(SessionLocal)
        result = agg.run_aggregation()
        logger.info("Startup aggregation: %s", result)
    except Exception as e:
        logger.warning("Startup aggregation failed: %s", e)

    yield


# ─── FastAPI App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="DocQuality Monitor API",
    description="Standalone monitoring backend for the DocQuality evaluation platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Database Dependency ───────────────────────────────────────────────────

def get_db():
    """Yield a DB session for request handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Mount Routes ──────────────────────────────────────────────────────────

from core.api.monitor_routes import create_monitor_router

monitor_router = create_monitor_router(get_db)
app.include_router(monitor_router)


@app.get("/")
def root():
    return {
        "service": "DocQuality Monitor",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "monitor"}


# ─── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MONITOR_PORT", "8001"))
    uvicorn.run("monitor_main:app", host="0.0.0.0", port=port, reload=True)
