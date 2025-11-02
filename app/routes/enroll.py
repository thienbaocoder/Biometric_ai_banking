from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict
import numpy as np
import logging

from ..services.pad_model import predict_prob_live
from ..services.face_embedding import extract
from ..database.queries import create_user, save_embedding, save_pose_embedding, add_log

router = APIRouter()
log = logging.getLogger("enroll")

class EnrollMultiReq(BaseModel):
    images: Dict[str, str] = Field(..., description="keys: front, left, right")
    phone: str | None = None
    email: str | None = None

POSE_THRESHOLDS = {"front": 0.50, "left": 0.25, "right": 0.25}

@router.post("/auth/register")
def register(req: EnrollMultiReq):
    required = {"front", "left", "right"}
    if not required.issubset(set(req.images.keys())):
        raise HTTPException(status_code=400, detail=f"ImagesMustContain:{sorted(required)}")

    # PAD theo từng pose: yêu cầu front pass và tổng >= 2 pose pass
    pad_scores, pad_passes = {}, {}
    for pose in ("front","left","right"):
        p = float(predict_prob_live(req.images[pose]))
        pad_scores[pose] = p
        pad_passes[pose] = bool(p >= POSE_THRESHOLDS[pose])

    if sum(pad_passes.values()) < 2 or not pad_passes["front"]:
        raise HTTPException(
            status_code=400,
            detail={"error":"LivenessFailed",
                    "need":">=2 poses pass (front required)",
                    "passes": pad_passes, "probs": pad_scores}
        )

    # Tạo user & lưu embedding
    user_id = create_user(phone=req.phone, email=req.email)
    vecs = {}
    for pose in ("front","left","right"):
        try:
            vec = extract(req.images[pose])
        except ValueError as e:
            # Nói rõ pose nào lỗi
            raise HTTPException(status_code=400, detail=f"{str(e)}:{pose}")
        arr = np.asarray(vec, dtype=np.float32).reshape(-1)
        vecs[pose] = arr
        save_pose_embedding(user_id, pose, arr, "sface-128")

    mean_vec = np.mean(np.stack([vecs["front"], vecs["left"], vecs["right"]], axis=0), axis=0)
    save_embedding(user_id, mean_vec, "sface-128")

    try:
        add_log(user_id, None, "ENROLL", "PASS", purpose="ENROLL")
    except Exception as e:
        log.warning(f"add_log failed (non-blocking): {e}")

    return {"status":"Registered","userId":user_id,"pad_probs":pad_scores,"pad_passes":pad_passes}
