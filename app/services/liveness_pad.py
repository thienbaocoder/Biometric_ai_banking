import base64
def liveness_ok(image_b64: str) -> bool:
    try:
        base64.b64decode(image_b64, validate=True)
        return True
    except Exception:
        return False
