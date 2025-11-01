import time, numpy as np
from .db import get_conn

def create_user(phone=None, email=None) -> int:
    now = int(time.time())
    with get_conn() as c:
        cur = c.execute(
          "INSERT INTO Users(Phone,Email,Status,CreatedAt,UpdatedAt) VALUES (?,?, 'ACTIVE', ?, ?)",
          (phone, email, now, now)
        )
        return cur.lastrowid  # auto-increment id

# ----- SAVE: luôn ép phẳng (128,) và dim = vec.size -----

def save_embedding(user_id: int, vec: np.ndarray, model_version="sface-128"):
    now = int(time.time())
    v = np.asarray(vec, dtype=np.float32).reshape(-1)  # (128,)
    dim = int(v.size)
    l2 = float(np.linalg.norm(v) + 1e-9)
    with get_conn() as c:
        c.execute("""
        INSERT INTO UserEmbeddings(UserId, Vector, Dim, ModelVersion, L2Norm, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(UserId) DO UPDATE SET
          Vector=excluded.Vector, Dim=excluded.Dim,
          ModelVersion=excluded.ModelVersion, L2Norm=excluded.L2Norm,
          CreatedAt=excluded.CreatedAt;
        """, (user_id, v.tobytes(), dim, model_version, l2, now))

def save_pose_embedding(user_id: int, pose: str, vec: np.ndarray, model_version="sface-128"):
    now = int(time.time())
    v = np.asarray(vec, dtype=np.float32).reshape(-1)  # (128,)
    dim = int(v.size)
    l2 = float(np.linalg.norm(v) + 1e-9)
    with get_conn() as c:
        c.execute("""
        INSERT INTO PoseEmbeddings(UserId, Pose, Vector, Dim, ModelVersion, L2Norm, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(UserId, Pose) DO UPDATE SET
          Vector=excluded.Vector, Dim=excluded.Dim,
          ModelVersion=excluded.ModelVersion, L2Norm=excluded.L2Norm,
          CreatedAt=excluded.CreatedAt;
        """, (user_id, pose, v.tobytes(), dim, model_version, l2, now))

# ----- GET: đọc đúng số phần tử theo Dim, trả ndarray phẳng -----

def get_embedding(user_id: int):
    with get_conn() as c:
        row = c.execute(
            "SELECT Vector, Dim FROM UserEmbeddings WHERE UserId=?",
            (user_id,)
        ).fetchone()
        if not row: 
            return None
        buf = row["Vector"]
        dim = int(row["Dim"] or 0)
        arr = np.frombuffer(buf, dtype=np.float32)
        # fallback nếu Dim bị sai (ví dụ 1): dùng độ dài bytes/4
        if dim <= 0 or dim > arr.size:
            dim = arr.size
        return arr[:dim].astype(np.float32, copy=False).reshape(-1)

def get_pose_embeddings(user_id: int):
    with get_conn() as c:
        rows = c.execute(
            "SELECT Pose, Vector, Dim FROM PoseEmbeddings WHERE UserId=?",
            (user_id,)
        ).fetchall()
        out = {}
        for r in rows:
            buf = r["Vector"]
            dim = int(r["Dim"] or 0)
            arr = np.frombuffer(buf, dtype=np.float32)
            if dim <= 0 or dim > arr.size:
                dim = arr.size
            out[r["Pose"]] = arr[:dim].astype(np.float32, copy=False).reshape(-1)
        return out

def add_log(user_id, sim, decision, pad, purpose, ip=None, device=None, geo=None):
    now = int(time.time())
    with get_conn() as c:
        c.execute("""
        INSERT INTO AuthLogs(UserId, Similarity, Decision, PadResult, Purpose, Ip, DeviceInfo, Geo, At)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, sim, decision, pad, purpose, ip, device, geo, now))
