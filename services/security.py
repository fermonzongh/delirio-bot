import hmac
import hashlib
from core.settings import APP_SECRET

def verify_webhook_signature(body: bytes, header_signature: str) -> bool:
    """Verifica que el webhook provenga de Meta/Heyoo usando la firma HMAC-SHA256."""
    if not header_signature:
        return False

    # Calcula firma local
    expected_signature = 'sha256=' + hmac.new(
        APP_SECRET.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, header_signature)