from core.settings import LLM_PROVIDER
from services.llm_client import ask_claude, ask_gpt

# Mapa de proveedor -> función correspondiente
llm_ask_functions = {
    "claude": ask_claude,
    "openai": ask_gpt
}

async def get_llm_response(user_message: str, conversation: list) -> str:
    """
    Devuelve la respuesta del modelo LLM configurado.
    """
    ask_function = llm_ask_functions.get(LLM_PROVIDER)

    if not ask_function:
        raise ValueError(f"LLM Provider desconocido: {LLM_PROVIDER}")

    # Llama la función correspondiente
    return await ask_function(user_message, conversation)