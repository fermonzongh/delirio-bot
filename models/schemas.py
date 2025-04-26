from pydantic import BaseModel

# Modelo para activar/desactivar takeover humano
class TakeoverRequest(BaseModel):
    customer_phone: str
    activate: bool = True


# Modelo para enviar mensajes manualmente como negocio
class MessageRequest(BaseModel):
    to: str  # Número destino en formato WhatsApp
    message: str
