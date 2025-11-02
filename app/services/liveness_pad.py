# app/services/liveness_pad.py
from __future__ import annotations
from .pad_model import is_live

def liveness_ok(image_b64: str) -> tuple[bool, float]:
    ok, prob = is_live(image_b64)
    return ok, prob
