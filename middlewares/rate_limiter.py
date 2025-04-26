import time
from fastapi import Request
from fastapi.responses import JSONResponse

# Configuraciones
MAX_MESSAGES_PER_MINUTE = 10
WINDOW_SECONDS = 60

# Almacen de rate limiting en memoria
rate_limit_buckets = {}

async def limit_rate_per_phone(request: Request, call_next):
    """
    Middleware para limitar la cantidad de mensajes que un número puede enviar en un período de tiempo.
    """
    # Solo aplicar en POST al /webhook
    if request.url.path == "/webhook" and request.method == "POST":
        try:
            body = await request.json()
            phone_number = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        except (KeyError, IndexError, TypeError, ValueError):
            # Si no podemos parsear, dejamos pasar igual (no queremos bloquear cosas internas)
            return await call_next(request)

        now = time.time()
        bucket = rate_limit_buckets.get(phone_number, [])

        # Limpiamos timestamps viejos fuera del rango de ventana
        bucket = [timestamp for timestamp in bucket if now - timestamp <= WINDOW_SECONDS]

        if len(bucket) >= MAX_MESSAGES_PER_MINUTE:
            print(f"🚨 Rate Limit superado para {phone_number} ({len(bucket)} mensajes en {WINDOW_SECONDS} seg)")
            return JSONResponse(
                status_code=429,  # HTTP 429 Too Many Requests
                content={"detail": "Too many requests, please slow down."},
            )

        # Agregar nuevo mensaje al bucket
        bucket.append(now)
        rate_limit_buckets[phone_number] = bucket

    response = await call_next(request)
    return response
