from __future__ import annotations
import base64, io, os
import numpy as np
from PIL import Image
import cv2

MODEL_DIR = os.environ.get("OPENCV_MODEL_DIR", "models")
DETECTOR_WEIGHTS = os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx")
RECOG_WEIGHTS    = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")

_detector = None
_recognizer = None

def _ensure_models():
    missing = []
    if not os.path.isfile(DETECTOR_WEIGHTS):
        missing.append(DETECTOR_WEIGHTS)
    if not os.path.isfile(RECOG_WEIGHTS):
        missing.append(RECOG_WEIGHTS)
    if missing:
        raise FileNotFoundError(
            "Missing model files: \n" + "\n".join(missing) +
            "\nPlace them under ./models/ or set OPENCV_MODEL_DIR."
        )

def _init_models():
    global _detector, _recognizer
    if _detector is not None and _recognizer is not None:
        return
    _ensure_models()
    # YuNet detector (nhạy hơn: score_thresh=0.6)
    _detector = cv2.FaceDetectorYN.create(
        DETECTOR_WEIGHTS,
        "",
        (320, 320),
        0.6,   # score threshold
        0.3,   # nms threshold
        5000
    )
    _recognizer = cv2.FaceRecognizerSF.create(RECOG_WEIGHTS, "")

def _b64_to_bgr(image_b64: str) -> np.ndarray:
    raw = base64.b64decode(image_b64, validate=True)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    arr = np.array(img)              # RGB
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def _detect_largest_face(bgr: np.ndarray):
    # detect at original size
    h, w = bgr.shape[:2]
    _detector.setInputSize((w, h))
    out = _detector.detect(bgr)
    faces = out[1] if (out is not None and len(out) >= 2) else None
    if faces is None or len(faces) == 0:
        # Try upscale x2 if face is small
        up = cv2.resize(bgr, (w*2, h*2), interpolation=cv2.INTER_LINEAR)
        _detector.setInputSize((w*2, h*2))
        out2 = _detector.detect(up)
        faces2 = out2[1] if (out2 is not None and len(out2) >= 2) else None
        if faces2 is None or len(faces2) == 0:
            return None
        # pick largest on upscaled
        areas = (faces2[:,2] * faces2[:,3])
        idx = int(np.argmax(areas))
        f = faces2[idx]
        # map bbox/landmarks back to original scale
        bbox = (f[0]/2, f[1]/2, f[2]/2, f[3]/2)
        lmk = (f[4:14].reshape(5,2) / 2.0)
        return bbox, lmk

    # pick largest on original
    areas = (faces[:,2] * faces[:,3])
    idx = int(np.argmax(areas))
    f = faces[idx]
    bbox = f[0:4]
    lmk = f[4:14].reshape(5,2)
    return bbox, lmk

def extract(image_b64: str) -> np.ndarray:
    """
    Trả về embedding L2-normalized (float32), Dim=128 (SFace).
    Raise ValueError("NoFaceDetected") nếu không thấy khuôn mặt.
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
