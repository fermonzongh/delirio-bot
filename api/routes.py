import time

from fastapi import APIRouter, HTTPException, Request

from heyoo import WhatsApp

from core.settings import HEYOO_PHONE_ID, HEYOO_TOKEN, OWNER_PHONE_NUMBER
from services.security import verify_webhook_signature
from models.schemas import MessageRequest
from services.conversation import (
    add_to_conversation_history,
    get_conversation_history,
    is_human_takeover,
    load_takeover_status,
    set_human_takeover,
)
from core.settings import LLM_PROVIDER
from services.llm_client import needs_human_takeover, notify_owner
from services.llm_dispatcher import get_llm_response
from services.validators import validate_message_content, validate_phone_country, detect_prompt_injection

# Instanciar el cliente de WhatsApp
wa_client = WhatsApp(token=HEYOO_TOKEN, phone_number_id=HEYOO_PHONE_ID)

router = APIRouter()

@router.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == "HolaAI":
        return int(params.get("hub.challenge"))
    return "Token inválido", 403

@router.post("/webhook")
async def heyoo_webhook(request: Request):
    # 🚨 1. Verificar firma
    header_signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Hub-Signature")
    body = await request.body()

    if not verify_webhook_signature(body, header_signature):
        print("🚨 Webhook con firma inválida bloqueado")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 🚨 2. Parsear JSON
    try:
        data = await request.json()
        message_entry = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender_phone = message_entry["from"]

    except Exception as e:
        print(f"⚠️ Error al parsear mensaje: {e}")
        return {"status": "ignored"}, 200

    # 🚨 3. Validaciones

    # Validar país
    validation_country = validate_phone_country(sender_phone, wa_client)
    if not validation_country["valid"]:
        return {"status": validation_country["status"]}, 200

    # Validar tipo de mensaje
    message_type = message_entry.get("type")
    if message_type != "text":
        print(f"⚠️ Tipo de mensaje no soportado de {sender_phone}: {message_type}")
        wa_client.send_message("Solo puedo procesar mensajes de texto por ahora. 📄", sender_phone)
        return {"status": "unsupported_message_type"}, 200
    
    # Extraer mensaje de texto
    user_message = message_entry["text"]["body"]

    # Validar si es prompt injection
    if detect_prompt_injection(user_message):
        print(f"🚨 Intento de Prompt Injection detectado de {sender_phone}")
        wa_client.send_message("Tu mensaje no puede ser procesado. ¿Podrías reformularlo?", sender_phone)
        return {"status": "prompt_injection_blocked"}, 200


    # Validar contenido del mensaje
    validation_content = validate_message_content(user_message, sender_phone, wa_client)
    if not validation_content["valid"]:
        return {"status": validation_content["status"]}, 200

    # 🚀 4. Procesamiento de conversación
    add_to_conversation_history(sender_phone, "user", user_message)

    if is_human_takeover(sender_phone):
        print("👤 Human takeover activo")
        return {"status": "human takeover"}, 200

    if needs_human_takeover(user_message):
        set_human_takeover(sender_phone, True)
        print("👤 Activando human takeover")
        wa_client.send_message("Un humano se contactará contigo a la brevedad.", sender_phone)
        notify_owner(sender_phone, user_message)
        return {"status": "escalated"}, 200

    conversation = get_conversation_history(sender_phone)

    try:
        print("🧠 Consultando modelo IA")
        response_text = await get_llm_response(user_message, conversation)
    except Exception as e:
        print(f"⚠️ Error consultando IA: {e}")
        response_text = "Estamos experimentando dificultades. ¿Querés que te conecte con una persona?"

    add_to_conversation_history(sender_phone, "assistant", response_text)
    wa_client.send_message(response_text, sender_phone)

    # ✅ 5. Respuesta final
    return {"status": "responded"}, 200

@router.post("/send")
async def send_manual_message(request: MessageRequest):
    try:
        wa_client.send_message(request.message, request.to)
        add_to_conversation_history(request.to, "assistant", request.message)
        return {"success": True, "message": "Mensaje enviado correctamente"}
    except Exception as e:
        print(f"⚠️ Error enviando mensaje manual: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo enviar el mensaje: {str(e)}")
