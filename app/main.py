from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database.db import init_db
from .routes.enroll import router as enroll_router
from .routes.verify import router as verify_router
from .routes.metrics import router as metrics_router

app = FastAPI(title="Biometric Auth AI")
app.include_router(enroll_router)
app.include_router(verify_router)
app.include_router(metrics_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/health")
def health():
    return {"status":"ok"}
