import httpx
import asyncio

from heyoo import WhatsApp

from services.drive import get_product_info_string
from core.settings import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    HEYOO_TOKEN,
    HEYOO_PHONE_ID,
    OWNER_PHONE_NUMBER
)
from core.logger import LoggerManager  # 🚀 Logger agregado

# Instanciar logger
log = LoggerManager(name="llm_client", level="INFO", log_to_file=False).get_logger()

# Inicializa cliente Heyoo
wa_client = WhatsApp(token=HEYOO_TOKEN, phone_number_id=HEYOO_PHONE_ID)

# Tiempo máximo de espera para respuestas externas (en segundos)
HTTP_TIMEOUT = 30.0

SYSTEM_PROMPT = """
Eres Kitu 🌶️, un asistente virtual especializado exclusivamente en productos de Delirio Picante, una tienda virtual de salsas picantes producidas en Argentina.

Los productos son salsas de diferentes variedades y sabores, con una escala de picante del 0 al 8.

Delirio Picante no cuenta con local físico. Realiza envíos a domicilio (a cargo del cliente) o entregas en puntos fijos en Godoy Cruz o Guaymallén, Mendoza.

---

⚡ Tu única función es responder preguntas **relacionadas exclusivamente** con:

- Productos
- Precios
- Características de los productos
- Disponibilidad general
- Pedido de catálogo

**No debes responder temas que estén fuera de estos puntos.**

Si el cliente solicita ayuda sobre:

- Programación
- Tecnología
- Creación de bots
- Marketing
- Redes sociales
- Cualquier otro tema ajeno a productos

➡️ **Debes amablemente negarte** y decir:  
_"Lo siento, sólo puedo ayudarte con temas de productos de Delirio Picante. Para otras consultas, por favor comunícate con nuestro equipo humano."_

---

⚠️ **Reglas estrictas que debes seguir:**

0. Debes presentarte y saludar solo la primera vez que hables como Kitu 🌶️.
1. Sé conciso, claro y amigable en tus respuestas.
2. Nunca intentes dar respuestas técnicas o fuera del negocio.
3. No inventes información sobre productos que no estén en la lista proporcionada.
4. Si te piden un pedido de productos, indica que debe realizarse por WhatsApp al **2616214868**.
5. Si te solicitan el catálogo, proporciona el enlace correspondiente.
6. No menciones cuántos productos quedan en stock. Solo indica si un producto está no disponible (stock cero).
7. No debes decir que eres una inteligencia artificial. Eres parte del equipo de Delirio Picante (aunque no es necesario aclararlo explícitamente).
8. No improvises temas fuera del listado. Siempre limita tu asistencia al negocio y sus productos.
9. Si te piden la ubicacion de Guaymallen, envía este enlace **https://maps.app.goo.gl/AaEGVC3bZpCm2f337**.
10. Si te piden la ubicación de Godoy Cruz, envía este enlace **https://maps.app.goo.gl/8NND6N4KGRcXLgGN6**.

Algo IMPORTANTE: Si ya saludaste en mensajes previos al cliente, no vuelvas a hacerlo. Mantén la conversación fluida y natural.

---

Recuerda:  
**Si no estás absolutamente seguro de que la pregunta es sobre productos de Delirio Picante, debes derivar al equipo humano.**
Algo IMPORTANTE: Si ya saludaste en mensajes previos al cliente, no vuelvas a hacerlo. Mantén la conversación fluida y natural.
"""

async def ask_claude(user_message, conversation_history):
    messages = []

    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": user_message})

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        log.info("🧠 Llamando a Claude API")
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 500,
                    "system": SYSTEM_PROMPT + "\n\n" + get_product_info_string(),
                    "messages": messages
                }
            )
            response.raise_for_status()
            result = response.json()
            log.info("✅ Respuesta recibida de Claude")
            return result["content"][0]["text"]

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            log.error(f"❌ Error llamando a Claude API: {e}")
            return "No puedo responder en este momento. ¿Querés que te conecte con una persona?"

async def ask_gpt(user_message, conversation_history, retries=3):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + get_product_info_string()}
    ]

    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": user_message})

    for attempt in range(retries):
        try:
            # 🌶️ Acá haces la request como ya la hacías
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": OPENAI_MODEL,
                        "messages": messages,
                        "temperature": 0.5,
                        "max_tokens": 500,
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt  # Exponential backoff
                log.warning(f"⏳ Rate limit alcanzado, reintentando en {wait_time} segundos...")
                await asyncio.sleep(wait_time)
            else:
                log.error(f"❌ Error consultando OpenAI: {e}")
                break
        except Exception as e:
            log.error(f"❌ Error inesperado con OpenAI: {e}")
            break

    # 🚨 Si llegamos acá es porque falló GPT
    log.warning(f"⚠️ Fallaron {retries} intentos con OpenAI. Probando fallback a Claude...")
    
    try:
        claude_response = await ask_claude(user_message, conversation_history)
        log.info(f"✅ Claude respondió exitosamente en fallback.")
        return claude_response
    except Exception as e:
        log.error(f"❌ Error también consultando Claude: {e}")
        return "Actualmente estamos experimentando dificultades. ¿Querés que te conecte con una persona?"

def needs_human_takeover(message: str) -> bool:
    keywords = [
        "human", "persona", "representante", "hablar con alguien", "quiero hablar con", "necesito ayuda humana"
    ]
    msg = message.lower()
    return any(kw in msg for kw in keywords)

async def call_claude_simple(prompt: str) -> str:
    """
    Llama a Claude directamente sin usar SYSTEM_PROMPT.
    Solo para tareas internas como resumen, clasificación, etc.
    """
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 500,
                    "system": "Eres un asistente que realiza tareas técnicas de resumen de texto.",
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"].strip()
        except Exception as e:
            log.error(f"❌ Error en llamada simple a Claude: {e}")
            return "No se pudo procesar."

async def call_gpt_simple(prompt: str, retries: int = 3) -> str:
    """
    Llama a GPT sin agregar prompts de sistema. 
    Solo para tareas internas como resumir, clasificar, etc.
    """
    for attempt in range(retries):
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": OPENAI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,  # 🔥 Más bajita para que sea más factual
                        "max_tokens": 500,
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 2 ** attempt  # Exponential backoff
                    log.warning(f"⏳ Rate limit alcanzado, reintentando en {wait_time} segundos...")
                    await asyncio.sleep(wait_time)
                else:
                    log.error(f"❌ Error consultando OpenAI: {e}")
                    break
            except Exception as e:
                log.error(f"❌ Error inesperado con OpenAI: {e}")
                break

    # 🚨 Si llegamos acá es porque falló GPT
    log.warning(f"⚠️ Fallaron {retries} intentos con OpenAI. Probando fallback a Claude...")
    
    try:
        claude_response = await call_claude_simple(prompt)
        log.info(f"✅ Claude respondió exitosamente en fallback.")
        return claude_response
    except Exception as e:
        log.error(f"❌ Error también consultando Claude: {e}")

    return "No se pudo generar un resumen."
        
async def get_summary_from_conversation_history(conversation_history):
    if not conversation_history:
        return "No hay conversación para resumir."

    history_text = ""
    for msg in conversation_history:
        role = "Cliente" if msg["role"] == "user" else "Bot"
        content = msg["content"]
        history_text += f"{role}: {content}\n"

    resumen_prompt = f"""
        Actúa como un sistema de resumen.

        Resume en máximo 100 palabras el siguiente historial de conversación entre cliente y bot.

        Historial:
        {history_text}
    """

    try:
        resumen = await call_gpt_simple(resumen_prompt)
        return resumen
    except Exception as e:
        log.error(f"❌ Error generando resumen de conversación: {e}")
        return "No se pudo generar un resumen."


async def notify_owner(customer_phone: str, conversation_history: str) -> None:
    message = await get_summary_from_conversation_history(conversation_history)
    wa_client.send_message(
        f"⚠️ El cliente {customer_phone} pidió hablar con una persona.\nMensaje: {message}",
        OWNER_PHONE_NUMBER  # Usamos variable correcta
    )
    log.info(f"📢 Notificación enviada al owner sobre {customer_phone}")
