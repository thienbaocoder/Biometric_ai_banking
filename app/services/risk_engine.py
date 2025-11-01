PASS_LOGIN      = 0.80
STEPUP_LOGIN    = 0.70

PASS_PAYMENT    = 0.83   # chặt hơn cho giao dịch
STEPUP_PAYMENT  = 0.78

def decide(sim: float, purpose: str = "LOGIN"):
    if purpose == "PAYMENT":
        if sim >= PASS_PAYMENT: return "ALLOW"
        if sim >= STEPUP_PAYMENT: return "STEP_UP"
        return "DENY"
    else:
        if sim >= PASS_LOGIN: return "ALLOW"
        if sim >= STEPUP_LOGIN: return "STEP_UP"
        return "DENY"
