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
    email: str = Field(..., description="Email dùng để đăng nhập")
    password: str = Field(..., description="Mật khẩu đăng nhập")
    phone: str | None = None


POSE_THRESHOLDS = {"front": 0.50, "left": 0.25, "right": 0.25}


@router.post("/auth/register")
def register(req: EnrollMultiReq):
    required = {"front", "left", "right"}
    if not required.issubset(set(req.images.keys())):
        raise HTTPException(
            status_code=400,
            detail=f"ImagesMustContain:{sorted(required)}"
        )

    # Validation đơn giản phía backend (frontend đã check trước)
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="EmailAndPasswordRequired")
    if len(req.password) < 6:
        # Đề phòng trường hợp frontend bị skip, đảm bảo không tạo account với pass quá ngắn
        raise HTTPException(status_code=400, detail="PasswordTooShort")

    # ----- PAD theo từng pose: yêu cầu front pass và tổng >= 2 pose pass -----
    pad_scores: Dict[str, float] = {}
    pad_passes: Dict[str, bool] = {}

    for pose in ("front", "left", "right"):
        p = float(predict_prob_live(req.images[pose]))
        pad_scores[pose] = p
        pad_passes[pose] = bool(p >= POSE_THRESHOLDS[pose])

    if sum(pad_passes.values()) < 2 or not pad_passes["front"]:
        # Thất bại liveness → trả thông tin chi tiết cho UI
        raise HTTPException(
            status_code=400,
            detail={
                "error": "LivenessFailed",
                "need": ">=2 poses pass (front required)",
                "passes": pad_passes,
                "probs": pad_scores,
            },
        )

    # ----- Tạo user & lưu embedding (có email + password) -----
    try:
        # create_user() phải nhận thêm password (đã hash bên trong)
        user_id = create_user(
            phone=req.phone,
            email=req.email,
            password=req.password,
        )
    except Exception as e:
        # Ví dụ sau này thêm UNIQUE(email) mà bị trùng, sẽ rơi vào đây
        log.error(f"CreateUserFailed: {e}")
        raise HTTPException(status_code=400, detail="CreateUserFailed")

    # ----- Trích embedding cho từng pose -----
    vecs: Dict[str, np.ndarray] = {}
    for pose in ("front", "left", "right"):
        try:
            vec = extract(req.images[pose])
        except ValueError as e:
            # Nói rõ pose nào lỗi cho UI
            raise HTTPException(
                status_code=400,
                detail=f"{str(e)}:{pose}",
            )
        arr = np.asarray(vec, dtype=np.float32).reshape(-1)
        vecs[pose] = arr
        save_pose_embedding(user_id, pose, arr, "sface-128")

    # Vector “tổng hợp” 3 pose
    mean_vec = np.mean(
        np.stack([vecs["front"], vecs["left"], vecs["right"]], axis=0),
        axis=0,
    )
    save_embedding(user_id, mean_vec, "sface-128")

    # Ghi log ENROLL (non-blocking)
    try:
        add_log(user_id, None, "ENROLL", "PASS", purpose="ENROLL")
    except Exception as e:
        log.warning(f"add_log failed (non-blocking): {e}")

    return {
        "status": "Registered",
        "userId": user_id,
        "pad_probs": pad_scores,
        "pad_passes": pad_passes,
    }
