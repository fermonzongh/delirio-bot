import httpx
import asyncio
from typing import List, Dict, Any, Optional
from heyoo import WhatsApp

from services.drive import drive_service
from core.settings import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    HEYOO_TOKEN,
    HEYOO_PHONE_ID,
    OWNER_PHONE_NUMBER
)
from core.logger import LoggerManager

class LLMClient:
    """A client for interacting with Language Model APIs (OpenAI GPT and Anthropic Claude)."""
    
    _instance = None
    
    # System prompt as class constant
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
    4. Si te preguntan por información de un producto, revisa la descripción del producto también.
    5. Si te piden un pedido de productos, indica que debe realizarse por WhatsApp al **2616214868**.
    6. Si te solicitan el catálogo, proporciona el enlace correspondiente.
    7. No menciones cuántos productos quedan en stock. Solo indica si un producto está no disponible (stock cero).
    8. No debes decir que eres una inteligencia artificial. Eres parte del equipo de Delirio Picante (aunque no es necesario aclararlo explícitamente).
    9. No improvises temas fuera del listado. Siempre limita tu asistencia al negocio y sus productos.
    10. Si te piden la ubicacion de Guaymallen, envía este enlace **https://maps.app.goo.gl/AaEGVC3bZpCm2f337**.
    11. Si te piden la ubicación de Godoy Cruz, envía este enlace **https://maps.app.goo.gl/8NND6N4KGRcXLgGN6**.

    Algo IMPORTANTE: Si ya saludaste en mensajes previos al cliente, no vuelvas a hacerlo. Mantén la conversación fluida y natural.

    ---

    Recuerda:  
    **Si no estás absolutamente seguro de que la pregunta es sobre productos de Delirio Picante, debes derivar al equipo humano.**
    Algo IMPORTANTE: Si ya saludaste en mensajes previos al cliente, no vuelvas a hacerlo. Mantén la conversación fluida y natural.
    """

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super(LLMClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the LLM client with required services and configurations."""
        if self._initialized:
            return
            
        self.log = LoggerManager(name="llm_client", level="INFO", log_to_file=False).get_logger()
        self.wa_client = WhatsApp(token=HEYOO_TOKEN, phone_number_id=HEYOO_PHONE_ID)
        self.http_timeout = 30.0
        self.max_retries = 3
        self._initialized = True

    async def _make_http_request(self, url: str, headers: Dict[str, str], json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make an HTTP request with timeout handling.
        
        Args:
            url: The endpoint URL
            headers: Request headers
            json_data: Request body as JSON
            
        Returns:
            Dict containing the response JSON
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            response = await client.post(url, headers=headers, json=json_data)
            response.raise_for_status()
            return response.json()

    async def ask_claude(self, user_message: str, conversation_history: List[Dict[str, Any]]) -> str:
        """Send a request to Claude API and get the response.
        
        Args:
            user_message: The user's input message
            conversation_history: List of previous messages in the conversation
            
        Returns:
            str: Claude's response text
        """
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in conversation_history]
        messages.append({"role": "user", "content": user_message})

        try:
            self.log.info("🧠 Llamando a Claude API")
            response = await self._make_http_request(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json_data={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 500,
                    "system": self.SYSTEM_PROMPT + "\n\n" + drive_service.get_product_info_string(),
                    "messages": messages
                }
            )
            self.log.info("✅ Respuesta recibida de Claude")
            return response["content"][0]["text"]
        except Exception as e:
            self.log.error(f"❌ Error llamando a Claude API: {e}")
            return "No puedo responder en este momento. ¿Querés que te conecte con una persona?"

    async def ask_gpt(self, user_message: str, conversation_history: List[Dict[str, Any]]) -> str:
        """Send a request to GPT API with retry logic.
        
        Args:
            user_message: The user's input message
            conversation_history: List of previous messages in the conversation
            
        Returns:
            str: GPT's response text, or falls back to Claude if GPT fails
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT + "\n\n" + drive_service.get_product_info_string()}
        ]
        messages.extend([{"role": msg["role"], "content": msg["content"]} for msg in conversation_history])
        messages.append({"role": "user", "content": user_message})

        for attempt in range(self.max_retries):
            try:
                response = await self._make_http_request(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json_data={
                        "model": OPENAI_MODEL,
                        "messages": messages,
                        "temperature": 0.5,
                        "max_tokens": 500,
                    }
                )
                return response["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 2 ** attempt
                    self.log.warning(f"⏳ Rate limit alcanzado, reintentando en {wait_time} segundos...")
                    await asyncio.sleep(wait_time)
                else:
                    self.log.error(f"❌ Error consultando OpenAI: {e}")
                    break
            except Exception as e:
                self.log.error(f"❌ Error inesperado con OpenAI: {e}")
                break

        # Fallback to Claude
        self.log.warning(f"⚠️ Fallaron {self.max_retries} intentos con OpenAI. Probando fallback a Claude...")
        try:
            claude_response = await self.ask_claude(user_message, conversation_history)
            self.log.info("✅ Claude respondió exitosamente en fallback.")
            return claude_response
        except Exception as e:
            self.log.error(f"❌ Error también consultando Claude: {e}")
            return "Actualmente estamos experimentando dificultades. ¿Querés que te conecte con una persona?"

    @staticmethod
    def needs_human_takeover(message: str) -> bool:
        """Check if the message indicates a need for human intervention.
        
        Args:
            message: The user's message to check
            
        Returns:
            bool: True if human intervention is needed
        """
        keywords = [
            "human", "persona", "representante", "hablar con alguien", 
            "quiero hablar con", "necesito ayuda humana"
        ]
        msg = message.lower()
        return any(kw in msg for kw in keywords)

    async def call_llm_simple(self, prompt: str, use_claude: bool = False) -> str:
        """Make a simple LLM call without system prompt.
        
        Args:
            prompt: The input prompt
            use_claude: Whether to use Claude instead of GPT
            
        Returns:
            str: The LLM's response
        """
        if use_claude:
            return await self._call_claude_simple(prompt)
        return await self._call_gpt_simple(prompt)

    async def _call_claude_simple(self, prompt: str) -> str:
        """Make a simple call to Claude API.
        
        Args:
            prompt: The input prompt
            
        Returns:
            str: Claude's response
        """
        try:
            response = await self._make_http_request(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json_data={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 500,
                    "system": "Eres un asistente que realiza tareas técnicas de resumen de texto.",
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            return response["content"][0]["text"].strip()
        except Exception as e:
            self.log.error(f"❌ Error en llamada simple a Claude: {e}")
            return "No se pudo procesar."

    async def _call_gpt_simple(self, prompt: str) -> str:
        """Make a simple call to GPT API with retries.
        
        Args:
            prompt: The input prompt
            
        Returns:
            str: GPT's response, or falls back to Claude if GPT fails
        """
        for attempt in range(self.max_retries):
            try:
                response = await self._make_http_request(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json_data={
                        "model": OPENAI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 500,
                    }
                )
                return response["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = 2 ** attempt
                    self.log.warning(f"⏳ Rate limit alcanzado, reintentando en {wait_time} segundos...")
                    await asyncio.sleep(wait_time)
                else:
                    self.log.error(f"❌ Error consultando OpenAI: {e}")
                    break
            except Exception as e:
                self.log.error(f"❌ Error inesperado con OpenAI: {e}")
                break

        # Fallback to Claude
        self.log.warning(f"⚠️ Fallaron {self.max_retries} intentos con OpenAI. Probando fallback a Claude...")
        return await self._call_claude_simple(prompt)

    async def get_summary_from_conversation_history(self, conversation_history: List[Dict[str, Any]]) -> str:
        """Generate a summary from conversation history.
        
        Args:
            conversation_history: List of previous messages in the conversation
            
        Returns:
            str: A summary of the conversation
        """
        if not conversation_history:
            return "Sin historial de conversación."

        prompt = "Resume esta conversación de manera concisa:\n\n"
        for msg in conversation_history[-10:]:  # Last 10 messages only
            prompt += f"{msg['role']}: {msg['content']}\n"

        return await self.call_llm_simple(prompt)

    async def notify_owner(self, customer_phone: str, conversation_history: List[Dict[str, Any]]) -> None:
        """Notify the owner about a conversation that needs attention.
        
        Args:
            customer_phone: The customer's phone number
            conversation_history: List of previous messages in the conversation
        """
        summary = await self.get_summary_from_conversation_history(conversation_history)
        message = f"🚨 *Atención requerida*\n\nCliente: {customer_phone}\n\nResumen:\n{summary}"
        
        try:
            self.wa_client.send_message(
                message=message,
                recipient_id=OWNER_PHONE_NUMBER
            )
            self.log.info(f"✅ Notificación enviada al dueño sobre {customer_phone}")
        except Exception as e:
            self.log.error(f"❌ Error notificando al dueño: {e}")

# Create a singleton instance
llm_client = LLMClient()
