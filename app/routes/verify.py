from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from typing import List, Dict
import numpy as np, random, time, uuid

from ..services.liveness_pad import liveness_ok
from ..services.face_embedding import extract
from ..services.risk_engine import decide
from ..services.jwt_token import issue
from ..database.queries import get_pose_embeddings, add_log

router = APIRouter()

def _pad_check(image_b64: str) -> tuple[bool, float]:
    res = liveness_ok(image_b64)
    if isinstance(res, tuple):
        ok, prob = bool(res[0]), float(res[1])
    else:
        ok, prob = bool(res), (1.0 if res else 0.0)
    return ok, prob

def _to_vec128(x) -> np.ndarray:
    v = np.asarray(x, dtype=np.float32).reshape(-1)
    if v.size == 512:
        raise HTTPException(status_code=409, detail="DimMismatch:512_vs_128_ReEnrollRequired")
    if v.size != 128:
        raise HTTPException(status_code=500, detail=f"UnexpectedDim:{v.size}")
    return v

def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    if a.size != b.size:
        raise HTTPException(status_code=409, detail=f"DimMismatch:{a.size}_vs_{b.size}")
    return float(np.dot(a, b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-9))

class VerifyStartReq(BaseModel):
    userId: int
    purpose: str  # LOGIN | PAYMENT

class VerifyStartResp(BaseModel):
    challengeId: str
    purpose: str
    sequence: List[str]

class VerifySubmitReq(BaseModel):
    challengeId: str
    frames: List[Dict[str, str]]  # [{pose, imageBase64}]

CHALLENGES: Dict[str, Dict] = {}

@router.post("/auth/verify/start", response_model=VerifyStartResp)
def verify_start(req: VerifyStartReq):
    poses = ["front","left","right"]
    random.shuffle(poses)
    cid = uuid.uuid4().hex
    CHALLENGES[cid] = {"userId": req.userId, "sequence": poses, "purpose": req.purpose, "ts": time.time()}
    return VerifyStartResp(challengeId=cid, purpose=req.purpose, sequence=poses)

@router.post("/auth/verify/submit")
def verify_submit(
    req: VerifySubmitReq,
    request: Request,
    gt: str | None = Query(None, description="lab only: 'bona' or 'spoof'"),
    atk: str | None = Query(None, description="lab only: 'print'|'replay'|'mask'|..."),
):
    t0 = time.perf_counter()

    ch = CHALLENGES.get(req.challengeId)
    if not ch:
        raise HTTPException(status_code=400, detail="InvalidChallenge")
    user_id = ch["userId"]; seq = ch["sequence"]; purpose = ch["purpose"]

    enrolled_raw = get_pose_embeddings(user_id)
    if set(enrolled_raw.keys()) != {"front","left","right"}:
        raise HTTPException(status_code=404, detail="UserNotEnrolled")
    enrolled = {k: _to_vec128(v) for k, v in enrolled_raw.items()}

    if len(req.frames) != len(seq):
        raise HTTPException(status_code=400, detail="FramesNotMatchSequence")

    sims, pad_probs, pad_flags = [], [], []
    for expected, frame in zip(seq, req.frames):
        if frame.get("pose") != expected:
            raise HTTPException(status_code=400, detail=f"WrongPoseOrder:{expected}")

        img = frame.get("imageBase64", "")

        # 1) PAD
        pad_ok, p_live = _pad_check(img)
        pad_probs.append(float(p_live))
        pad_flags.append(bool(pad_ok))

        # 2) Embedding
        try:
            probe = extract(img)
        except ValueError as e:
            if "NoFaceDetected" in str(e):
                # Trả về 400 rõ ràng cho UI, đồng thời log forensics nhẹ
                try:
                    add_log(user_id, None, "DENY", "FAIL", purpose,
                            ip=(request.client.host if request.client else None),
                            attack_type="no_face",
                            duration_ms=int((time.perf_counter()-t0)*1000))
                except Exception as _:
                    pass
                raise HTTPException(status_code=400, detail="NoFaceDetected")
            raise HTTPException(status_code=400, detail=str(e))

        sims.append(cosine(probe, enrolled[expected]))

    sim_min = float(min(sims))
    pad_min = float(min(pad_probs))
    pad_max = float(max(pad_probs))
    pad_avg = float(sum(pad_probs)/len(pad_probs))
    pad_passed = int(all(pad_flags))

    dec = decide(sim_min, purpose=purpose) if "purpose" in decide.__code__.co_varnames else decide(sim_min)
    if dec == "FAIL":
        dec = "DENY"
    if not pad_passed:
        dec = "STEP_UP" if purpose == "LOGIN" else "DENY"

    duration_ms = int((time.perf_counter() - t0) * 1000)
    is_bona = None if gt is None else (1 if gt.lower()=="bona" else 0)

    # Ghi log – không để lỗi log làm hỏng flow
    try:
        add_log(
            user_id, sim_min, dec,
            "PASS" if pad_passed else "FAIL", purpose,
            ip=(request.client.host if request.client else None),
            pad_prob_min=pad_min, pad_prob_max=pad_max, pad_prob_avg=pad_avg,
            pad_passed=pad_passed, is_bona=is_bona, attack_type=atk, duration_ms=duration_ms
        )
    except Exception as e:
        print(f"add_log failed (non-blocking): {e}")

    CHALLENGES.pop(req.challengeId, None)

    if dec == "ALLOW":
        return {
            "purpose": purpose,
            "token": issue(str(user_id)),
            "similarity_min": sim_min,
            "similarities": sims,
            "pad_prob_min": pad_min, "pad_prob_max": pad_max, "pad_prob_avg": pad_avg,
            "pad_probs": pad_probs
        }
    if dec == "STEP_UP":
        return {
            "purpose": purpose,
            "stepUp": "OTP_REQUIRED",
            "similarity_min": sim_min,
            "similarities": sims,
            "pad_prob_min": pad_min, "pad_prob_max": pad_max, "pad_prob_avg": pad_avg,
            "pad_probs": pad_probs
        }

    # DENY
    raise HTTPException(status_code=400, detail={
        "error": "VerifyFailed",
        "similarity_min": sim_min, "similarities": sims,
        "pad_prob_min": pad_min, "pad_prob_max": pad_max, "pad_prob_avg": pad_avg,
        "pad_probs": pad_probs
    })
