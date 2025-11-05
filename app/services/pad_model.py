# app/services/pad_model.py
import os
import base64
import onnxruntime as ort
import numpy as np
import cv2

# ---- Config ----
_MODEL_PATH = "models/face_antispoof.onnx"                # model PAD
_YUNET_PATH = "models/face_detection_yunet_2023mar.onnx"  # YuNet
_LIVE_INDEX = 1  # đa số model 2 lớp: index 1 = live

# ---- Globals ----
_SESSION = None
_INPUT_NAME = None
_OUTPUT_NAME = None
_EXPECT_SHAPE = None  # (N, C, H, W) hoặc dynamic
_DET = None           # YuNet detector nếu có


def _ensure_session():
    """
    Khởi tạo session ONNX (PAD) + YuNet, chỉ làm 1 lần.
    Dùng nội bộ và cho init_pad_model().
    """
    global _SESSION, _INPUT_NAME, _OUTPUT_NAME, _EXPECT_SHAPE, _DET

    if _SESSION is None:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"[PAD] Model not found at '{_MODEL_PATH}'. "
                "Hãy kiểm tra lại đường dẫn hoặc đặt file vào thư mục models/"
            )
        _SESSION = ort.InferenceSession(
            _MODEL_PATH,
            providers=["CPUExecutionProvider"],
        )
        _INPUT_NAME = _SESSION.get_inputs()[0].name
        _OUTPUT_NAME = _SESSION.get_outputs()[0].name
        _EXPECT_SHAPE = _SESSION.get_inputs()[0].shape  # [1, 3, H, W] hoặc dynamic
        print(f"[PAD] Loaded model: {_MODEL_PATH}")
        print(f"[PAD] IO names: input={_INPUT_NAME}, output={_OUTPUT_NAME}")
        print(f"[PAD] Expected input shape: {_EXPECT_SHAPE}")

    if _DET is None and os.path.exists(_YUNET_PATH):
        try:
            # YuNet detector (OpenCV FaceDetectorYN)
            _DET = cv2.FaceDetectorYN.create(
                _YUNET_PATH,
                "",
                (320, 320),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000,
            )
            print("[PAD] YuNet loaded for face crop.")
        except Exception as e:
            _DET = None
            print(f"[PAD] YuNet unavailable ({e}), fallback to no-crop.")


def init_pad_model() -> None:
    """
    Hàm public để gọi ở main.py (startup) nếu muốn warm-up model.
    Không bắt buộc, vì predict_prob_live() cũng tự gọi _ensure_session().
    """
    _ensure_session()


def _decode_base64_to_bgr(image_b64: str) -> np.ndarray:
    """
    Decode base64 (có thể là raw hoặc 'data:image/jpeg;base64,...') -> BGR.
    Raise ValueError('BadImageDecode') nếu lỗi.
    """
    try:
        # Hỗ trợ cả dataURL lẫn raw base64
        payload = image_b64.split(",")[-1].strip()
        data = base64.b64decode(payload, validate=False)
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("BadImageDecode")
        return img
    except Exception as e:
        raise ValueError(f"BadImageDecode:{e}") from e


def _crop_face(img_bgr: np.ndarray) -> np.ndarray | None:
    """
    Crop khuôn mặt lớn nhất bằng YuNet (nếu có).
    Trả None nếu không phát hiện.
    """
    if _DET is None:
        return None
    h, w = img_bgr.shape[:2]
    _DET.setInputSize((w, h))
    ret, faces = _DET.detect(img_bgr)
    if faces is None or len(faces) == 0:
        return None

    # Lấy face lớn nhất
    areas = faces[:, 2] * faces[:, 3]
    i = int(np.argmax(areas))
    x, y, ww, hh = faces[i][:4].astype(int)

    # Margin khi crop
    m = int(0.35 * max(ww, hh))
    x0 = max(0, x - m)
    y0 = max(0, y - m)
    x1 = min(w, x + ww + m)
    y1 = min(h, y + hh + m)
    return img_bgr[y0:y1, x0:x1].copy()


def _infer_target_size() -> int:
    """
    Đoán H=W mong đợi từ shape input model. Mặc định 112 nếu không rõ.
    """
    try:
        # shape kiểu [1,3,H,W] hoặc [None,3,112,112]
        h = _EXPECT_SHAPE[2]
        w = _EXPECT_SHAPE[3]
        if isinstance(h, int) and isinstance(w, int) and h == w and h > 0:
            return int(h)
    except Exception:
        pass
    return 112  # fallback an toàn cho nhiều model anti-spoof


def _preprocess(image_b64: str) -> np.ndarray:
    """
    Decode, crop (nếu có), resize theo size model yêu cầu, chuẩn hóa -> NCHW float32 [0..1].
    """
    img = _decode_base64_to_bgr(image_b64)

    face = _crop_face(img)
    if face is None:
        # Fallback: dùng ảnh gốc (demo). Production nên raise "NoFace" để UI báo rõ.
        face = img

    size = _infer_target_size()  # 112 hoặc 224
    face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
    face = cv2.resize(face, (size, size), interpolation=cv2.INTER_AREA)

    x = face.astype(np.float32) / 255.0  # (H, W, 3)
    x = np.transpose(x, (2, 0, 1))       # (3, H, W)
    x = np.expand_dims(x, axis=0)        # (1, 3, H, W)
    return x


def _to_prob_live(out: np.ndarray) -> float:
    """
    Chuẩn hóa output -> xác suất 'live' (0..1).
    Hỗ trợ:
    - 1 giá trị (coi là prob_live)
    - vector 2 lớp (logits hoặc probability)
    """
    y = out.squeeze()
    if y.ndim == 0:
        p_live = float(y)
    else:
        y = y.astype(np.float32)
        # Nếu không trông giống probability -> coi là logits -> softmax
        if y.sum() <= 0.0 or np.any(y < 0) or np.any(y > 1):
            y = y - np.max(y)
            y = np.exp(y) / np.sum(np.exp(y))
        idx = _LIVE_INDEX if y.shape[0] > _LIVE_INDEX else 0
        p_live = float(y[idx])

    return max(0.0, min(1.0, p_live))


def predict_prob_live(image_b64: str) -> float:
    """
    Trả về xác suất live (0..1), lấy max giữa:
    - A) crop khuôn mặt (YuNet)
    - B) full-frame (no-crop)
    """
    _ensure_session()

    # A) với crop
    x1 = _preprocess(image_b64)
    out1 = _SESSION.run([_OUTPUT_NAME], {_INPUT_NAME: x1})[0]
    p1 = _to_prob_live(out1)

    # B) no-crop: resize trực tiếp toàn ảnh
    img = _decode_base64_to_bgr(image_b64)
    size = _infer_target_size()
    frame = cv2.cvtColor(cv2.resize(img, (size, size)), cv2.COLOR_BGR2RGB)
    x2 = np.expand_dims(
        np.transpose(frame.astype(np.float32) / 255.0, (2, 0, 1)),
        0,
    )
    out2 = _SESSION.run([_OUTPUT_NAME], {_INPUT_NAME: x2})[0]
    p2 = _to_prob_live(out2)

    return max(p1, p2)


def is_live(image_b64: str, threshold: float = 0.5) -> tuple[bool, float]:
    """
    Trả về (ok, prob_live) với ngưỡng threshold.
    """
    p = predict_prob_live(image_b64)
    return p >= threshold, p
