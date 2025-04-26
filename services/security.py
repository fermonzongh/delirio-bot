import hmac
import hashlib

from core.settings import APP_SECRET
from core.logger import LoggerManager  # 🚀 Logger agregado

# Instanciar logger
log = LoggerManager(name="security", level="DEBUG", log_to_file=False).get_logger()

def verify_webhook_signature(body: bytes, header_signature: str) -> bool:
    """Verifica que el webhook provenga de Meta/Heyoo usando la firma HMAC-SHA256."""
    if not header_signature:
        log.warning("⚠️ No se encontró la cabecera de firma en el webhook")
        return False

    try:
        # Calcula firma local
        expected_signature = 'sha256=' + hmac.new(
            APP_SECRET.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()

        valid = hmac.compare_digest(expected_signature, header_signature)

        if not valid:
            log.warning("⚠️ Firma del webhook inválida")
        else:
            log.debug("✅ Firma del webhook validada correctamente")

        return valid

    except Exception as e:
        log.error(f"❌ Error al verificar la firma del webhook: {e}")
        return False
