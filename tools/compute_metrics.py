import json, argparse
import numpy as np

def far_frr_eer(items):
    # chỉ xét các bản ghi có nhãn bona (1/0) và có sim
    rows = [r for r in items if r.get("bona") in (0,1) and r.get("sim") is not None]
    if not rows:
        return {"eer": None, "thr_at_eer": None}
    sims = np.array([float(r["sim"]) for r in rows], dtype=np.float32)
    bona = np.array([int(r["bona"]) for r in rows], dtype=np.int32).astype(bool)

    ths = np.linspace(sims.min(), sims.max(), 400, dtype=np.float32)
    fars, frrs = [], []
    for t in ths:
        FAR = np.mean(sims[~bona] >= t) if np.any(~bona) else 0.0
        FRR = np.mean(sims[bona]  <  t) if np.any(bona)  else 0.0
        fars.append(FAR); frrs.append(FRR)
    fars, frrs = np.array(fars), np.array(frrs)
    i = int(np.argmin(np.abs(fars - frrs)))
    return {"eer": float((fars[i]+frrs[i])/2), "thr_at_eer": float(ths[i])}

def apcer_bpcer_acer(items, pad_thr=0.85):
    # APCER: % spoof bị nhận nhầm là live (pad_ok True)
    # BPCER: % bona-fide bị nhận nhầm là spoof (pad_ok False)
    rows = [r for r in items if r.get("bona") in (0,1) and r.get("pad_prob") is not None]
    if not rows:
        return {"APCER": None, "BPCER": None, "ACER": None}
    # Nếu pad_ok đã được log thì dùng, còn không thì so pad_prob>=thr
    pred_live = []
    bona = []
    for r in rows:
        if r.get("pad_ok") in (0,1):
            ok = bool(r["pad_ok"])
        else:
            ok = float(r["pad_prob"]) >= pad_thr
        pred_live.append(ok)
        bona.append(bool(r["bona"]))
    pred_live = np.array(pred_live)
    bona = np.array(bona)

    # Attack = bona==False
    atk_mask = ~bona
    live_mask = bona

    APCER = float(np.mean(pred_live[atk_mask])) if np.any(atk_mask) else None
    BPCER = float(np.mean(~pred_live[live_mask])) if np.any(live_mask) else None
    if APCER is None or BPCER is None:
        ACER = None
    else:
        ACER = float((APCER + BPCER) / 2.0)
    return {"APCER": APCER, "BPCER": BPCER, "ACER": ACER}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="metrics export JSON file")
    ap.add_argument("--pad-thr", type=float, default=0.85)
    args = ap.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        payload = json.load(f)
    items = payload["items"] if isinstance(payload, dict) and "items" in payload else payload

    m1 = far_frr_eer(items)
    m2 = apcer_bpcer_acer(items, pad_thr=args.pad_thr)

    print("=== Verification (matching) ===")
    print(f"EER: {m1['eer']:.4f} @ thr={m1['thr_at_eer']:.4f}" if m1["eer"] is not None else "No data")
    print("\n=== PAD (anti-spoof) ===")
    if m2["APCER"] is not None:
        print(f"APCER: {m2['APCER']:.4f}")
        print(f"BPCER: {m2['BPCER']:.4f}")
        print(f"ACER : {m2['ACER']:.4f}")
    else:
        print("No data for PAD metrics")

if __name__ == "__main__":
    main()
