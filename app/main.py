from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database.db import init_db
from .routes.enroll import router as enroll_router
from .routes.verify import router as verify_router
from .routes.metrics import router as metrics_router
from .services.pad_model import init_pad_model
from .services.face_embedding import init_face_models

app = FastAPI(title="Biometric Auth AI")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(enroll_router)
app.include_router(verify_router)
app.include_router(metrics_router)


@app.on_event("startup")
def _startup():
  init_db()
  print("[STARTUP] DB ok")
  try:
      init_pad_model()
      print("[STARTUP] PAD model ok")
  except Exception as e:
      print(f"[STARTUP] PAD init failed: {e}")
  try:
      init_face_models()
      print("[STARTUP] Face models ok")
  except Exception as e:
      print(f"[STARTUP] Face init failed: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}
