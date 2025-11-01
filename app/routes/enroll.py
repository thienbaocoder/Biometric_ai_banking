from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict
from ..services.liveness_pad import liveness_ok
from ..services.face_embedding import extract
from ..database.queries import create_user, save_embedding, save_pose_embedding, add_log
import numpy as np

router = APIRouter()

class EnrollMultiReq(BaseModel):
    images: Dict[str, str] = Field(..., description="keys: front, left, right")
    phone: str | None = None
    email: str | None = None

@router.post("/auth/register")
def register(req: EnrollMultiReq):
    required = {"front","left","right"}
    if set(req.images.keys()) != required:
        raise HTTPException(status_code=400, detail=f"images must contain {required}")
    # PAD mock: ảnh hợp lệ Base64
    for k,v in req.images.items():
        if not liveness_ok(v):
            raise HTTPException(status_code=400, detail=f"LivenessFailed:{k}")

    user_id = create_user(phone=req.phone, email=req.email)

    vecs = {}
    for pose, img in req.images.items():
        try:
            vec = extract(img)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"{str(e)}:{pose}")
        vecs[pose] = vec
        save_pose_embedding(user_id, pose, vec, "sface-128")

    mean_vec = np.mean(np.stack(list(vecs.values()), axis=0), axis=0)
    save_embedding(user_id, mean_vec, "sface-128")
    add_log(user_id, None, "ENROLL", "PASS", purpose="ENROLL")

    return {"status": "Registered", "userId": user_id}

