import os, time, jwt
SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-32bytes")
ISS = "bank.example"; AUD = "bank.web"; EXP = 30*60

def issue(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iss": ISS, "aud": AUD, "iat": now, "exp": now+EXP}
    return jwt.encode(payload, SECRET, algorithm="HS256")
