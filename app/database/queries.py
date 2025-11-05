import time
import os
import hmac
import base64
import hashlib
import numpy as np

from .db import get_conn


# ---------- PASSWORD UTILS ----------

def _hash_password(password: str, salt_b64: str | None = None) -> tuple[str, str]:
    """
    Trả về (salt_b64, hash_b64) dùng PBKDF2-HMAC-SHA256.
    """
    if salt_b64 is None:
        salt = os.urandom(16)
    else:
        salt = base64.b64decode(salt_b64.encode("utf-8"))

    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000,
    )
    return (
        base64.b64encode(salt).decode("utf-8"),
        base64.b64encode(dk).decode("utf-8"),
    )


def _verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    expected = base64.b64decode(hash_b64.encode("utf-8"))
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000,
    )
    return hmac.compare_digest(dk, expected)


# ---------- USERS / EMBEDDINGS ----------

def create_user(phone=None, email=None, password: str | None = None) -> int:
    """
    Tạo user mới, nếu có password thì hash và lưu vào Users.
    """
    now = int(time.time())
    pw_hash = None
    pw_salt = None
    if password:
        pw_salt, pw_hash = _hash_password(password)

    with get_conn() as c:
        cur = c.execute(
            """
            INSERT INTO Users(Phone,Email,Status,CreatedAt,UpdatedAt,PasswordHash,PasswordSalt)
            VALUES (?,?, 'ACTIVE', ?, ?, ?, ?)
            """,
            (phone, email, now, now, pw_hash, pw_salt),
        )
        return cur.lastrowid


def get_user_by_email(email: str):
    with get_conn() as c:
        return c.execute("SELECT * FROM Users WHERE Email=?", (email,)).fetchone()


def authenticate_user(email: str, password: str):
    """
    Trả về userId nếu email/password đúng, ngược lại trả None.
    """
    row = get_user_by_email(email)
    if not row:
        return None
    salt = row["PasswordSalt"]
    pw_hash = row["PasswordHash"]
    if not salt or not pw_hash:
        return None
    if _verify_password(password, salt, pw_hash):
        return row["UserId"]
    return None


def save_embedding(user_id: int, vec: np.ndarray, model_version="sface-128"):
    now = int(time.time())
    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    dim = int(v.size)
    l2 = float(np.linalg.norm(v) + 1e-9)
    with get_conn() as c:
        c.execute(
            """
        INSERT INTO UserEmbeddings(UserId, Vector, Dim, ModelVersion, L2Norm, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(UserId) DO UPDATE SET
          Vector=excluded.Vector, Dim=excluded.Dim,
          ModelVersion=excluded.ModelVersion, L2Norm=excluded.L2Norm,
          CreatedAt=excluded.CreatedAt;
        """,
            (user_id, v.tobytes(), dim, model_version, l2, now),
        )


def save_pose_embedding(user_id: int, pose: str, vec: np.ndarray, model_version="sface-128"):
    now = int(time.time())
    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    dim = int(v.size)
    l2 = float(np.linalg.norm(v) + 1e-9)
    with get_conn() as c:
        c.execute(
            """
        INSERT INTO PoseEmbeddings(UserId, Pose, Vector, Dim, ModelVersion, L2Norm, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(UserId, Pose) DO UPDATE SET
          Vector=excluded.Vector, Dim=excluded.Dim,
          ModelVersion=excluded.ModelVersion, L2Norm=excluded.L2Norm,
          CreatedAt=excluded.CreatedAt;
        """,
            (user_id, pose, v.tobytes(), dim, model_version, l2, now),
        )


def get_embedding(user_id: int):
    with get_conn() as c:
        row = c.execute("SELECT Vector, Dim FROM UserEmbeddings WHERE UserId=?", (user_id,)).fetchone()
        if not row:
            return None
        buf = row["Vector"]
        dim = int(row["Dim"] or 0)
        arr = np.frombuffer(buf, dtype=np.float32)
        if dim <= 0 or dim > arr.size:
            dim = arr.size
        return arr[:dim].astype(np.float32, copy=False).reshape(-1)


def get_pose_embeddings(user_id: int):
    with get_conn() as c:
        rows = c.execute("SELECT Pose, Vector, Dim FROM PoseEmbeddings WHERE UserId=?", (user_id,)).fetchall()
        out = {}
        for r in rows:
            buf = r["Vector"]
            dim = int(r["Dim"] or 0)
            arr = np.frombuffer(buf, dtype=np.float32)
            if dim <= 0 or dim > arr.size:
                dim = arr.size
            out[r["Pose"]] = arr[:dim].astype(np.float32, copy=False).reshape(-1)
        return out


# ---- Logging: chèn theo cột đang tồn tại để không bao giờ vỡ INSERT ----

def _existing_authlog_columns():
    with get_conn() as c:
        return [r["name"] for r in c.execute("PRAGMA table_info(AuthLogs);")]


def add_log(
    user_id,
    similarity,
    decision,
    pad_result,
    purpose,
    ip=None,
    device_info=None,
    geo=None,
    pad_prob_min=None,
    pad_prob_max=None,
    pad_prob_avg=None,
    pad_passed=None,
    is_bona=None,
    attack_type=None,
    duration_ms=None,
):
    cols = _existing_authlog_columns()
    fields = ["UserId", "Similarity", "Decision", "PadResult", "Purpose", "Ip", "DeviceInfo", "Geo", "At"]
    values = [user_id, similarity, decision, pad_result, purpose, ip, device_info, geo, int(time.time())]

    extra_map = {
        "PadProbMin": pad_prob_min,
        "PadProbMax": pad_prob_max,
        "PadProbAvg": pad_prob_avg,
        "PadPassed":  pad_passed,
        "IsBonaFide": is_bona,
        "AttackType": attack_type,
        "DurationMs": duration_ms,
    }
    for k, v in extra_map.items():
        if k in cols:
            idx = fields.index("At")
            fields.insert(idx, k)
            values.insert(idx, v)

    sql = f"INSERT INTO AuthLogs ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})"
    with get_conn() as c:
        c.execute(sql, tuple(values))
