from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from compliance.main import app as compliance_app
from banking.main import app as banking_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database initialization for all workspaces on startup.

    Sub-app lifespans do NOT fire when mounted via app.mount(),
    so we must handle init centrally here.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Initialize compliance database (creates tables + runs migrations)
    from compliance.database import init_db as compliance_init_db
    compliance_init_db()
    logger.info("Compliance database initialized.")

    # Initialize banking database (creates tables + runs migrations)
    from banking.database import init_db as banking_init_db
    banking_init_db()
    logger.info("Banking database initialized.")

    yield


app = FastAPI(
    title="Unified Document Quality APIs",
    description="Mounts both Compliance and Banking APIs",
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

app.mount("/compliance", compliance_app)
app.mount("/banking", banking_app)

@app.get("/")
def read_root():
    return {"message": "Unified System Online", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

