import sqlite3
from pathlib import Path
from typing import Dict

# DB ngay tại root project: .../biometric_auth_ai/biometric.db
DB_PATH = (Path(__file__).resolve().parents[2] / "biometric.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# Các cột mở rộng cho log
_AUTHLOGS_EXTRA_COLS: Dict[str, str] = {
    "PadProbMin": "REAL",
    "PadProbMax": "REAL",
    "PadProbAvg": "REAL",
    "PadPassed":  "INTEGER",      # 0/1
    "IsBonaFide": "INTEGER",      # lab: 0/1/NULL
    "AttackType": "TEXT",         # lab
    "DurationMs": "INTEGER",
    # Ip/DeviceInfo/Geo đã có sẵn trong schema gốc
}

# Các cột mở rộng cho Users (mật khẩu)
_USERS_EXTRA_COLS: Dict[str, str] = {
    "PasswordHash": "TEXT",
    "PasswordSalt": "TEXT",
}


def _ensure_authlogs_columns(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(AuthLogs)")
    existing = {row[1] for row in cur.fetchall()}
    for col, typ in _AUTHLOGS_EXTRA_COLS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE AuthLogs ADD COLUMN {col} {typ}")
    conn.commit()


def _ensure_users_columns(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(Users)")
    existing = {row[1] for row in cur.fetchall()}
    for col, typ in _USERS_EXTRA_COLS.items():    # <- ĐÚNG: 1 dấu _
        if col not in existing:
            cur.execute(f"ALTER TABLE Users ADD COLUMN {col} {typ}")
    conn.commit()



def init_db():
    schema = """
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS Users(
      UserId       INTEGER PRIMARY KEY AUTOINCREMENT,
      Phone        TEXT,
      Email        TEXT,
      PasswordHash TEXT,
      PasswordSalt TEXT,
      Status       TEXT NOT NULL DEFAULT 'ACTIVE',
      CreatedAt    INTEGER NOT NULL,
      UpdatedAt    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS UserEmbeddings(
      UserId       INTEGER PRIMARY KEY REFERENCES Users(UserId) ON DELETE CASCADE,
      Vector       BLOB NOT NULL,
      Dim          INTEGER NOT NULL,
      ModelVersion TEXT NOT NULL,
      L2Norm       REAL NOT NULL,
      CreatedAt    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS PoseEmbeddings(
      UserId       INTEGER NOT NULL REFERENCES Users(UserId) ON DELETE CASCADE,
      Pose         TEXT NOT NULL CHECK (Pose IN ('front','left','right')),
      Vector       BLOB NOT NULL,
      Dim          INTEGER NOT NULL,
      ModelVersion TEXT NOT NULL,
      L2Norm       REAL NOT NULL,
      CreatedAt    INTEGER NOT NULL,
      PRIMARY KEY (UserId, Pose)
    );

    CREATE TABLE IF NOT EXISTS AuthLogs(
      LogId       INTEGER PRIMARY KEY AUTOINCREMENT,
      UserId      INTEGER REFERENCES Users(UserId) ON DELETE SET NULL,
      Similarity  REAL,
      Decision    TEXT NOT NULL CHECK (Decision IN ('ALLOW','STEP_UP','DENY','ENROLL')),
      PadResult   TEXT,
      Purpose     TEXT,   -- LOGIN / PAYMENT / ENROLL
      Ip          TEXT,
      DeviceInfo  TEXT,
      Geo         TEXT,
      At          INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS OtpChallenges(
      OtpId       TEXT PRIMARY KEY,
      UserId      INTEGER NOT NULL REFERENCES Users(UserId) ON DELETE CASCADE,
      Purpose     TEXT NOT NULL CHECK (Purpose IN ('LOGIN','PAYMENT','PROFILE')),
      CodeHash    TEXT NOT NULL,
      ExpiresAt   INTEGER NOT NULL,
      ConsumedAt  INTEGER,
      CreatedAt   INTEGER NOT NULL
    );
    """
    with get_conn() as conn:
        conn.executescript(schema)
        _ensure_authlogs_columns(conn)
        _ensure_users_columns(conn)
    print(f"[DB] Using database at: {DB_PATH}")
