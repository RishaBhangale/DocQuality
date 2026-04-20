from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from compliance.main import app as compliance_app
from banking.main import app as banking_app

app = FastAPI(
    title="Unified Document Quality APIs",
    description="Mounts both Compliance and Banking APIs",
    version="1.0.0"
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
