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

# Inicializa cliente Heyoo
wa_client = WhatsApp(token=HEYOO_TOKEN, phone_number_id=HEYOO_PHONE_ID)

# Tiempo máximo de espera para respuestas externas (en segundos)
HTTP_TIMEOUT = 30.0

SYSTEM_PROMPT = """
Eres Kitu, un asistente virtual para un negocio de venta (no elaboracion) salsas picantes producidos en Argentina.
Los productos son salsas picantes de diferentes variedades y sabores, en una escala de picante del 0 al 8.
El negocio se llama Delirio Picante. es de venta virtual, no tenemos local fisico por el momento, realizamos envios a domicilio a cargo del cliente o entregas en nuestros domicilios en Godoy Cruz o Guaymallen.
Tu función es ayudar a los clientes respondiendo preguntas sobre los productos, precios y realizando pedidos.

Sigue estas reglas importantes:
0. Deberás presentarte la primera vez que hables, eres Kitu 🌶️.
1. Sé conciso, claro y amigable en tus respuestas.
2. Si no sabes algo, sugiere que el cliente hable con una persona del equipo.
3. No inventes información sobre productos que no estén en la lista proporcionada.
4. Cuando un cliente quiera hacer un pedido, recopilá los productos y cantidades que desea.
5. Si el cliente pide el catálogo, proporcioná el enlace correspondiente.
6. Mantené las respuestas por debajo de las 200 palabras para que sean fáciles de leer en WhatsApp.
7. No debes mencionar cuantos productos quedan en stock, pero si un producto tiene 0 stock, debes decir que no está disponible.

No menciones que sos una IA. Sos parte del equipo del negocio de salsas picantes, aunque no hace falta que lo menciones.
"""

async def ask_claude(user_message, conversation_history):

    messages = []

    for msg in conversation_history:
        messages.append({
            "role": msg["role"],   # "user" o "assistant"
            "content": msg["content"]
        })

    # Último mensaje del usuario
    messages.append({"role": "user", "content": user_message})

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        print("🧠 Llamando a Claude API")
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
                    "system": SYSTEM_PROMPT + "\n\n" + get_product_info_string(),  # este es el prompt de instrucciones
                    "messages": messages  # solo los mensajes user/assistant
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            print(f"[Claude API Error] {e}")
            return "No puedo responder en este momento. ¿Querés que te conecte con una persona?"


async def ask_gpt(user_message, conversation_history):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + get_product_info_string()}
    ]

    for msg in conversation_history:
        messages.append({
            "role": msg["role"],  # "user" o "assistant"
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": user_message})

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        print("🧠 Llamando a OpenAI API")
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
            return result["choices"][0]["message"]["content"]
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            print(f"[OpenAI API Error] {e}")
            return "No puedo responder en este momento. ¿Querés que te conecte con una persona?"


def needs_human_takeover(message: str) -> bool:
    keywords = [
        "human", "persona", "representante", "hablar con alguien", "quiero hablar con", "necesito ayuda humana"
    ]
    msg = message.lower()
    return any(kw in msg for kw in keywords)

def notify_owner(customer_phone: str, message: str) -> None:
    wa_client.send_message(
        f"⚠️ El cliente {customer_phone} pidió hablar con una persona.\nMensaje: {message}",
        54261156214868 #OWNER_PHONE_NUMBER
    )
