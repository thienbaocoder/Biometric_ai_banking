import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "biometric.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    schema = """
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS Users(
      UserId     INTEGER PRIMARY KEY AUTOINCREMENT,
      Phone      TEXT,
      Email      TEXT,
      Status     TEXT NOT NULL DEFAULT 'ACTIVE',
      CreatedAt  INTEGER NOT NULL,
      UpdatedAt  INTEGER NOT NULL
    );

    -- Vector “tổng hợp” để verify 1 ảnh (giữ tương thích)
    CREATE TABLE IF NOT EXISTS UserEmbeddings(
      UserId      INTEGER PRIMARY KEY REFERENCES Users(UserId) ON DELETE CASCADE,
      Vector      BLOB NOT NULL,
      Dim         INTEGER NOT NULL,
      ModelVersion TEXT NOT NULL,
      L2Norm      REAL NOT NULL,
      CreatedAt   INTEGER NOT NULL
    );

    -- Lưu theo tư thế
    CREATE TABLE IF NOT EXISTS PoseEmbeddings(
      UserId      INTEGER NOT NULL REFERENCES Users(UserId) ON DELETE CASCADE,
      Pose        TEXT NOT NULL CHECK (Pose IN ('front','left','right')),
      Vector      BLOB NOT NULL,
      Dim         INTEGER NOT NULL,
      ModelVersion TEXT NOT NULL,
      L2Norm      REAL NOT NULL,
      CreatedAt   INTEGER NOT NULL,
      PRIMARY KEY (UserId, Pose)
    );

    CREATE TABLE IF NOT EXISTS AuthLogs(
      LogId       INTEGER PRIMARY KEY AUTOINCREMENT,
      UserId      INTEGER REFERENCES Users(UserId) ON DELETE SET NULL,
      Similarity  REAL,
      Decision    TEXT NOT NULL CHECK (Decision IN ('ALLOW','STEP_UP','DENY','ENROLL')),
      PadResult   TEXT,
      Purpose     TEXT, -- LOGIN/PAYMENT
      Ip          TEXT, DeviceInfo TEXT, Geo TEXT,
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
    with get_conn() as c:
        c.executescript(schema)
