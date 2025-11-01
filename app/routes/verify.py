from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any
import numpy as np, random, time, uuid, json

from ..services.liveness_pad import liveness_ok
from ..services.face_embedding import extract
from ..services.risk_engine import decide
from ..services.jwt_token import issue
from ..database.queries import get_pose_embeddings, add_log

router = APIRouter()

# ------------------ utils ------------------

def _to_vec128(x) -> np.ndarray:
    import json, numpy as np

    def _from_any(y):
        # y -> ndarray phẳng nếu có thể
        if isinstance(y, np.ndarray):
            return y.reshape(-1).astype(np.float32, copy=False)
        if isinstance(y, (list, tuple)):
            return np.asarray(y, dtype=np.float32).reshape(-1)
        if isinstance(y, (bytes, bytearray)):
            # giả định raw float32
            cnt = len(y) // 4
            return np.frombuffer(y, dtype=np.float32, count=cnt).reshape(-1)
        if isinstance(y, str):
            s = y.strip()
            # case 1: JSON "[...]" hoặc "[[...]]"
            if s.startswith("[") and s.endswith("]"):
                try:
                    obj = json.loads(s)
                    return np.asarray(obj, dtype=np.float32).reshape(-1)
                except json.JSONDecodeError:
                    pass
            # case 2: chuỗi "0.1,0.2,..." -> tách theo dấu phẩy
            if "," in s:
                arr = [float(t) for t in s.split(",") if t.strip()!=""]
                return np.asarray(arr, dtype=np.float32).reshape(-1)
            # trường hợp còn lại: không rõ định dạng
            raise HTTPException(status_code=500, detail="BadEmbeddingString")
        # loại không hỗ trợ
        raise HTTPException(status_code=500, detail=f"UnsupportedEmbeddingType:{type(y).__name__}")

    v = _from_any(x)

    # nếu bị lồng một lớp: v.size==1 và phần tử bên trong là str/bytes/list -> bóc thêm 1 lần
    if v.size == 1:
        inner = None
        # lấy phần tử gốc (không cast sang float) để thử bóc tiếp
        if isinstance(x, (list, tuple)) and len(x) == 1:
            inner = x[0]
        elif isinstance(x, np.ndarray) and x.size == 1:
            inner = x.item()
        if isinstance(inner, (str, bytes, bytearray, list, tuple, np.ndarray)):
            v = _from_any(inner)

    v = v.reshape(-1)
    if v.size == 512:
        # dữ liệu cũ ArcFace -> yêu cầu enroll lại theo SFace 128-D
        raise HTTPException(status_code=409, detail="DimMismatch:512_vs_128_ReEnrollRequired")
    if v.size != 128:
        # báo kích thước thực để biết nguồn dữ liệu sai
        raise HTTPException(status_code=500, detail=f"UnexpectedDim:{v.size}")
    return v.astype(np.float32, copy=False)

def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32).reshape(-1)  # (128,)
    b = np.asarray(b, dtype=np.float32).reshape(-1)  # (128,)
    if a.size != b.size:
        raise HTTPException(status_code=409, detail=f"DimMismatch:{a.size}_vs_{b.size}")
    denom = (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
    return float(np.dot(a, b) / denom)

# ------------------ schemas ------------------

class VerifyStartReq(BaseModel):
    userId: int
    purpose: str  # "LOGIN" | "PAYMENT"

class VerifyStartResp(BaseModel):
    challengeId: str
    purpose: str
    sequence: List[str]

class VerifySubmitReq(BaseModel):
    challengeId: str
    frames: List[Dict[str, str]]  # [{pose, imageBase64}]

# ------------------ in-memory challenges ------------------

CHALLENGES: Dict[str, Dict] = {}

@router.post("/auth/verify/start", response_model=VerifyStartResp)
def verify_start(req: VerifyStartReq):
    poses = ["front", "left", "right"]
    random.shuffle(poses)
    cid = uuid.uuid4().hex
    CHALLENGES[cid] = {
        "userId": req.userId,
        "sequence": poses,
        "purpose": req.purpose,
        "ts": time.time()
    }
    return VerifyStartResp(challengeId=cid, purpose=req.purpose, sequence=poses)

@router.post("/auth/verify/submit")
def verify_submit(req: VerifySubmitReq, request: Request):
    ch = CHALLENGES.get(req.challengeId)
    if not ch:
        raise HTTPException(status_code=400, detail="InvalidChallenge")

    user_id = ch["userId"]
    seq = ch["sequence"]
    purpose = ch["purpose"]

    # đọc embeddings đã enroll và chuẩn hóa về (128,)
    enrolled_raw = get_pose_embeddings(user_id)  # expected keys: front/left/right
    if set(enrolled_raw.keys()) != {"front", "left", "right"}:
        raise HTTPException(status_code=404, detail="UserNotEnrolled")
    enrolled = {k: _to_vec128(v) for k, v in enrolled_raw.items()}

    if len(req.frames) != len(seq):
        raise HTTPException(status_code=400, detail="FramesNotMatchSequence")

    sims: List[float] = []
    for expected, frame in zip(seq, req.frames):
        if frame.get("pose") != expected:
            raise HTTPException(status_code=400, detail=f"WrongPoseOrder:{expected}")
        img = frame.get("imageBase64", "")
        if not liveness_ok(img):
            raise HTTPException(status_code=400, detail=f"LivenessFailed:{expected}")

        probe = extract(img)                      # có thể trả (1,128) hoặc (128,)
        probe = np.asarray(probe, np.float32).reshape(-1)  # ép về (128,)

        sims.append(cosine(probe, enrolled[expected]))

    # lấy tư thế yếu nhất làm aggregate
    agg = float(min(sims))

    # decide(agg, purpose) nếu có tham số purpose; fallback cho version cũ
    decision = decide(agg, purpose=purpose) if "purpose" in decide.__code__.co_varnames else decide(agg)

    add_log(user_id, agg, decision, "PASS", purpose, ip=request.client.host)
    CHALLENGES.pop(req.challengeId, None)

    if decision == "ALLOW":
        return {
            "purpose": purpose,
            "token": issue(str(user_id)),
            "similarity_min": agg,
            "similarities": sims
        }
    if decision == "STEP_UP":
        return {
            "purpose": purpose,
            "stepUp": "OTP_REQUIRED",
            "similarity_min": agg,
            "similarities": sims
        }

    # mặc định coi là FAIL
    raise HTTPException(
        status_code=400,
        detail={"error": "VerifyFailed", "similarity_min": agg, "similarities": sims}
    )
