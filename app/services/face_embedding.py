# app/services/face_embedding.py
from __future__ import annotations

import base64
import io
import os
from typing import Tuple

import numpy as np
from PIL import Image
import cv2

MODEL_DIR = os.environ.get("OPENCV_MODEL_DIR", "models")
DETECTOR_WEIGHTS = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
RECOG_WEIGHTS    = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")

_detector = None
_recognizer = None


def _ensure_models_exist():
    missing = []
    if not os.path.isfile(DETECTOR_WEIGHTS):
        missing.append(DETECTOR_WEIGHTS)
    if not os.path.isfile(RECOG_WEIGHTS):
        missing.append(RECOG_WEIGHTS)
    if missing:
        raise FileNotFoundError(
            "Missing model files:\n" + "\n".join(missing) +
            "\nPlace them under ./models/ or set OPENCV_MODEL_DIR."
        )


def _init_models():
    """
    Khởi tạo YuNet + SFace, chỉ làm 1 lần.
    """
    global _detector, _recognizer
    if _detector is not None and _recognizer is not None:
        return

    _ensure_models_exist()

    # YuNet detector
    _detector = cv2.FaceDetectorYN.create(
        DETECTOR_WEIGHTS,
        "",
        (320, 320),
        score_threshold=0.6,
        nms_threshold=0.3,
        top_k=5000,
    )
    # SFace recognizer
    _recognizer = cv2.FaceRecognizerSF.create(RECOG_WEIGHTS, "")
    print("[FACE] YuNet + SFace loaded.")


def init_face_models() -> None:
    """
    Hàm public để warm-up model từ main.py (startup). Không bắt buộc.
    """
    _init_models()


def _b64_to_bgr(image_b64: str) -> np.ndarray:
    """
    Decode base64 (hỗ trợ cả raw 'AAA...' và 'data:image/jpeg;base64,...') -> BGR.
    Raise ValueError nếu decode lỗi.
    """
    try:
        payload = image_b64.split(",")[-1].strip()
        raw = base64.b64decode(payload, validate=False)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.array(img)  # RGB
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        raise ValueError(f"BadImageDecode:{e}") from e


def _detect_largest_face(bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray] | None:
    """
    Detect khuôn mặt lớn nhất.
    Trả về (bbox, landmarks) hoặc None nếu không thấy.
    """
    h, w = bgr.shape[:2]
    _detector.setInputSize((w, h))
    out = _detector.detect(bgr)
    faces = out[1] if (out is not None and len(out) >= 2) else None

    if faces is None or len(faces) == 0:
        # Thử upscale x2 nếu mặt quá nhỏ
        up = cv2.resize(bgr, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)
        _detector.setInputSize((w * 2, h * 2))
        out2 = _detector.detect(up)
        faces2 = out2[1] if (out2 is not None and len(out2) >= 2) else None
        if faces2 is None or len(faces2) == 0:
            return None

        # Lấy face lớn nhất trên ảnh upscale
        areas = faces2[:, 2] * faces2[:, 3]
        idx = int(np.argmax(areas))
        f = faces2[idx]
        bbox = (f[0] / 2, f[1] / 2, f[2] / 2, f[3] / 2)
        lmk = (f[4:14].reshape(5, 2) / 2.0)
        return np.array(bbox, dtype=np.float32), lmk.astype(np.float32)

    # Lấy face lớn nhất trên ảnh gốc
    areas = faces[:, 2] * faces[:, 3]
    idx = int(np.argmax(areas))
    f = faces[idx]
    bbox = f[0:4]
    lmk = f[4:14].reshape(5, 2)
    return bbox.astype(np.float32), lmk.astype(np.float32)


def extract(image_b64: str) -> np.ndarray:
    """
    Trả về embedding L2-normalized (float32), Dim=128 (SFace).
    Raise ValueError("NoFaceDetected") nếu không thấy khuôn mặt.
    Raise ValueError("BadImageDecode:...") nếu ảnh lỗi.
    """
    _init_models()
    bgr = _b64_to_bgr(image_b64)

    det = _detect_largest_face(bgr)
    if det is None:
        raise ValueError("NoFaceDetected")
    _, kps = det

    aligned = _recognizer.alignCrop(bgr, kps)   # 112x112 BGR
    feat = _recognizer.feature(aligned)
    feat = feat / (np.linalg.norm(feat) + 1e-9)
    return feat.astype(np.float32)
