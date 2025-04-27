from fastapi import APIRouter, HTTPException, Request
from heyoo import WhatsApp

from core.settings import HEYOO_PHONE_ID, HEYOO_TOKEN
from core.logger import LoggerManager  # 🚀 Logger agregado
from models.schemas import MessageRequest
from services.security import verify_webhook_signature
from services.conversation import (
    add_to_conversation_history,
    get_conversation_history,
    get_name_from_conversation,
    is_human_takeover,
    load_takeover_status,
    set_human_takeover,
    save_takeover_status,
    set_customer_name,
)
from services.llm_client import needs_human_takeover, notify_owner
from services.llm_dispatcher import get_llm_response
from services.validators import validate_message_content, validate_phone_country, detect_prompt_injection, es_nombre_valido, is_real_name_with_gpt
from services.user_profiles import extract_name_with_llm  # Si estás usando LLM
from services.audio_processing import process_audio_message  # Si estás usando LLM

# Instanciar el cliente de WhatsApp
wa_client = WhatsApp(token=HEYOO_TOKEN, phone_number_id=HEYOO_PHONE_ID)

# Instanciar el logger
log = LoggerManager(name="routes", level="INFO", log_to_file=False).get_logger()

router = APIRouter()

@router.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == "HolaAI":
        return int(params.get("hub.challenge"))
    return "Token inválido", 403

@router.post("/webhook")
async def heyoo_webhook(request: Request):
    # 🚨 Verificar firma
    header_signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Hub-Signature")
    body = await request.body()

    if not verify_webhook_signature(body, header_signature):
        log.error("🚨 Webhook con firma inválida bloqueado")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 🚨 Parsear JSON
    try:
        data = await request.json()
        # 🚀 Parsear datos del mensaje
        value = data["entry"][0]["changes"][0]["value"]
        if "statuses" in value:
            # 📩 Caso de status de entrega
            status_entry = value["statuses"][0]
            status = status_entry.get("status")
            message_id = status_entry.get("id")
            recipient_id = status_entry.get("recipient_id")
            timestamp = status_entry.get("timestamp")

            log.debug(f"📩 Status recibido:")
            log.debug(f"  - Mensaje ID: {message_id}")
            log.debug(f"  - Estado: {status}")
            log.debug(f"  - Destinatario: {recipient_id}")
            log.debug(f"  - Timestamp: {timestamp}")

            return {"status": "status_logged"}, 200
        
        # 🚨 Si no es STATUS, validamos que tenga MENSAJE
        if "messages" not in value:
            log.warning("⚠️ Webhook sin 'messages' ni 'statuses'. Ignorando.")
            return {"status": "ignored"}, 200
        
        # 🚀 Caso normal de mensaje
        message_entry = value["messages"][0]
        sender_phone = message_entry["from"]

        # 🚨 Validaciones
        validation_country = validate_phone_country(sender_phone, wa_client)
        if not validation_country["valid"]:
            return {"status": validation_country["status"]}, 200
        
        if message_entry.get("type") != "text":
            if message_entry.get("type") == "audio":
                media_id = message_entry["audio"]["id"]
                user_message = await process_audio_message(media_id)
            elif message_entry.get("type") == "reaction":
                return {"status": "reaction_received"}, 200
            else:
                log.warning(f"⚠️ Mensaje no sorportado recibido de {sender_phone} tipo: {message_entry.get('type')}")
                wa_client.send_message("No puedo procesar este tipo de mensaje. ¿Podrías enviarme un mensaje de texto?", sender_phone)
                return {"status": "unsupported_media"}, 200
            
        else:
            user_message = message_entry["text"]["body"]
        
        if detect_prompt_injection(user_message):
            log.warning(f"🚨 Intento de Prompt Injection detectado de {sender_phone}")
            wa_client.send_message("Tu mensaje no puede ser procesado. ¿Podrías reformularlo?", sender_phone)
            return {"status": "prompt_injection_blocked"}, 200

        validation_content = validate_message_content(user_message, sender_phone, wa_client)
        if not validation_content["valid"]:
            return {"status": validation_content["status"]}, 200
        
        # 🚀 Extraer perfil
        profile_info = value.get("contacts", [{}])[0].get("profile", {})
        user_name = profile_info.get("name")

        # 🚀 Cargar historial
        conversation = get_conversation_history(sender_phone)

        # 🚀 Saludo inteligente
        saludo = None
        if not get_name_from_conversation(sender_phone):
            if not conversation:
                if user_name and es_nombre_valido(user_name):
                    if await is_real_name_with_gpt(user_name):
                        set_customer_name(sender_phone, user_name)
                        saludo = f"¡Hola {user_name}! Soy Kitu 🌶️ de Delirio Picante, ¿en qué puedo ayudarte?"
                    else:
                        saludo = "¡Hola! Soy Kitu 🌶️ de Delirio Picante. ¿Querés decirme tu nombre para reconocerte mejor en próximas consultas? 🌶️"
                else:
                    saludo = "¡Hola! Soy Kitu 🌶️ de Delirio Picante. ¿Querés decirme tu nombre para reconocerte mejor en próximas consultas? 🌶️"

                wa_client.send_message(saludo, sender_phone)
                add_to_conversation_history(sender_phone, "assistant", saludo)
                log.info(f"👋 Saludo enviado a {sender_phone}: {saludo}")

    except Exception as e:
        log.error(f"⚠️ Error al parsear mensaje o status: {e}")
        try:
            log.error(f"Payload recibido: {data['entry'][0]['changes'][0]['value']}")
        except:
            log.error("No se pudo imprimir el valor del webhook recibido.")
        return {"status": "ignored"}, 200

    # 🚀 Procesamiento de conversación
    add_to_conversation_history(sender_phone, "user", user_message)

    if saludo:
        add_to_conversation_history(sender_phone, "assistant", saludo)
    
    if not get_name_from_conversation(sender_phone):
        log.info(f"📝 Nombre no encontrado en conversación para {sender_phone}. Intentando extraer...")
        detected_name = await extract_name_with_llm(user_message)

        if detected_name:
            set_customer_name(sender_phone, detected_name)
            add_to_conversation_history(sender_phone, "assistant", f"Guardé tu nombre como {detected_name}")
            log.info(f"📝 Nombre aprendido para {sender_phone}: {detected_name}")

    if is_human_takeover(sender_phone):
        takeover_status = load_takeover_status()
        record = takeover_status.get(sender_phone, {})

        if not record.get("alerted", False):
            # Marcar como alertado
            record["alerted"] = True
            takeover_status[sender_phone] = record
            save_takeover_status(takeover_status)

        # 🚀 Seguimos procesando normalmente
        log.info(f"✅ Takeover activo para {sender_phone}, pero seguimos respondiendo normalmente.")


    if needs_human_takeover(user_message):
        set_human_takeover(sender_phone, True)
        log.info(f"👤 Activando human takeover para {sender_phone}")
        wa_client.send_message("Una persona se contactará contigo a la brevedad. Mientras tanto puedes consultar lo que necesites.", sender_phone)
        await notify_owner(sender_phone, get_conversation_history(sender_phone))
        return {"status": "escalated"}, 200

    conversation = get_conversation_history(sender_phone)

    try:
        log.info(f"🧠 Consultando modelo IA para {sender_phone}")
        response_text = await get_llm_response(user_message, conversation)
    except Exception as e:
        log.error(f"⚠️ Error consultando IA: {e}")
        response_text = "Estamos experimentando dificultades. ¿Querés que te conecte con una persona?"

    add_to_conversation_history(sender_phone, "assistant", response_text)

    wa_client.send_message(response_text, sender_phone)

    # ✅ Respuesta final
    return {"status": "responded"}, 200

@router.post("/send")
async def send_manual_message(request: MessageRequest):
    try:
        wa_client.send_message(request.message, request.to)
        add_to_conversation_history(request.to, "assistant", request.message)
        return {"success": True, "message": "Mensaje enviado correctamente"}
    except Exception as e:
        log.error(f"⚠️ Error enviando mensaje manual: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo enviar el mensaje: {str(e)}")
