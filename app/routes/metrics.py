# app/routes/metrics.py
from fastapi import APIRouter, Query
from ..database.db import get_conn

router = APIRouter()

@router.get("/metrics/export")
def export_metrics(t0: int | None = Query(None), t1: int | None = Query(None)):
    """
    Trả về các bản ghi cần cho đánh giá:
    Similarity (sim_min), IsBonaFide, PadProbMin, PadPassed, Decision, Purpose, AttackType, DurationMs, At
    Có thể truyền t0,t1 (epoch seconds) để lọc theo thời gian.
    """
    sql = """
    SELECT Similarity, IsBonaFide, PadProbMin, PadPassed, Decision, Purpose, AttackType, DurationMs, At
    FROM AuthLogs
    """
    args=[]
    if t0 is not None and t1 is not None:
        sql += " WHERE At BETWEEN ? AND ?"
        args=[t0, t1]
    with get_conn() as c:
        rows = c.execute(sql, args).fetchall()
        out=[]
        for r in rows:
            out.append({
                "sim": r["Similarity"],
                "bona": r["IsBonaFide"],
                "pad_prob": r["PadProbMin"],
                "pad_ok": r["PadPassed"],
                "decision": r["Decision"],
                "purpose": r["Purpose"],
                "atk": r["AttackType"],
                "dur_ms": r["DurationMs"],
                "at": r["At"],
            })
        return {"count": len(out), "items": out}
