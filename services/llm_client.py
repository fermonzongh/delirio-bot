import httpx
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
log = LoggerManager(name="llm_client", level="DEBUG", log_to_file=False).get_logger()

# Inicializa cliente Heyoo
wa_client = WhatsApp(token=HEYOO_TOKEN, phone_number_id=HEYOO_PHONE_ID)

# Tiempo máximo de espera para respuestas externas (en segundos)
HTTP_TIMEOUT = 30.0

SYSTEM_PROMPT = """
Eres Kitu 🌶️, un asistente virtual especializado exclusivamente en productos de Delirio Picante, una tienda virtual de salsas picantes producidas en Argentina.

Los productos son salsas de diferentes variedades y sabores, con una escala de picante del 0 al 8.

Delirio Picante trabaja únicamente de manera virtual, no cuenta con local físico. Realiza envíos a domicilio (a cargo del cliente) o entregas en puntos fijos en Godoy Cruz o Guaymallén, Mendoza.

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

0. Debes presentarte siempre la primera vez que hables como Kitu 🌶️.
1. Sé conciso, claro y amigable en tus respuestas.
2. Nunca intentes dar respuestas técnicas o fuera del negocio.
3. No inventes información sobre productos que no estén en la lista proporcionada.
4. Si te piden un pedido de productos, indica que debe realizarse por WhatsApp al **2616214868**.
5. Si te solicitan el catálogo, proporciona el enlace correspondiente.
6. No menciones cuántos productos quedan en stock. Solo indica si un producto está no disponible (stock cero).
7. No debes decir que eres una inteligencia artificial. Eres parte del equipo de Delirio Picante (aunque no es necesario aclararlo explícitamente).
8. No improvises temas fuera del listado. Siempre limita tu asistencia al negocio y sus productos.

---

Recuerda:  
**Si no estás absolutamente seguro de que la pregunta es sobre productos de Delirio Picante, debes derivar al equipo humano.**

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

async def ask_gpt(user_message, conversation_history):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + get_product_info_string()}
    ]

    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": user_message})

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        log.info("🧠 Llamando a OpenAI API")
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 500,
                }
            )
            response.raise_for_status()
            result = response.json()
            log.info("✅ Respuesta recibida de OpenAI")
            return result["choices"][0]["message"]["content"]

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            log.error(f"❌ Error llamando a OpenAI API: {e}")
            return "No puedo responder en este momento. ¿Querés que te conecte con una persona?"

def needs_human_takeover(message: str) -> bool:
    keywords = [
        "human", "persona", "representante", "hablar con alguien", "quiero hablar con", "necesito ayuda humana"
    ]
    msg = message.lower()
    return any(kw in msg for kw in keywords)

def notify_owner(customer_phone: str, message: str) -> None:
    print(type(OWNER_PHONE_NUMBER))
    wa_client.send_message(
        f"⚠️ El cliente {customer_phone} pidió hablar con una persona.\nMensaje: {message}",
        OWNER_PHONE_NUMBER  # Usamos variable correcta
    )
    log.info(f"📢 Notificación enviada al owner sobre {customer_phone}")
