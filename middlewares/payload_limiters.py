from fastapi import Request
from fastapi.responses import JSONResponse
from core.logger import LoggerManager  # 🚀 Logger agregado

# Instanciar logger
log = LoggerManager(name="payload_limiter", level="DEBUG", log_to_file=False).get_logger()

# Configuración: Tamaño máximo permitido (en bytes)
MAX_PAYLOAD_SIZE = 50 * 1024  # 50 KB

async def limit_payload_size(request: Request, call_next):
    """
    Middleware para limitar el tamaño del payload entrante.
    Rechaza requests demasiado grandes para proteger el bot.
    """
    body = await request.body()

    if len(body) > MAX_PAYLOAD_SIZE:
        log.warning(f"🚨 Payload rechazado: {len(body)} bytes (límite {MAX_PAYLOAD_SIZE} bytes)")
        return JSONResponse(
            status_code=413,  # HTTP 413 Payload Too Large
            content={"detail": "Request payload too large"}
        )

    # Guardamos el body para que otros puedan accederlo sin volver a leerlo
    request._body = body
    response = await call_next(request)
    return response
