import os
import json
import time
from typing import List, Dict, Any

from core.settings import CONVERSATION_HISTORY_DIR, TAKEOVER_FILE
from core.logger import LoggerManager  # 🚀 Logger agregado

# Instanciar logger
log = LoggerManager(name="conversation", level="DEBUG", log_to_file=True).get_logger()

# Asegurarse que el directorio exista
os.makedirs(CONVERSATION_HISTORY_DIR, exist_ok=True)

# Función utilitaria
def sanitize_phone(phone: str) -> str:
    return phone.replace(":", "_").replace("+", "").replace("whatsapp", "")

# -----------------------------
# Gestión de Takeover Humano
# -----------------------------
def load_takeover_status() -> Dict[str, dict]:
    if os.path.exists(TAKEOVER_FILE):
        try:
            with open(TAKEOVER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log.warning("⚠️ Error al leer el archivo de takeover, devolviendo vacío.")
            return {}
    return {}

def save_takeover_status(status_dict: Dict[str, dict]) -> None:
    try:
        with open(TAKEOVER_FILE, "w", encoding="utf-8") as f:
            json.dump(status_dict, f, ensure_ascii=False, indent=2)
        log.info("💾 Estado de takeover guardado correctamente.")
    except Exception as e:
        log.error(f"❌ Error al guardar el archivo de takeover: {e}")

def is_human_takeover(phone_number: str, expiration_seconds: int = 180) -> bool:
    status = load_takeover_status()
    record = status.get(phone_number)

    if record and record.get("active"):
        timestamp = record.get("timestamp", 0)
        elapsed = time.time() - timestamp
        if elapsed > expiration_seconds:
            log.warning(f"⚠️ Takeover expirado para {phone_number} después de {elapsed:.1f} segundos")
            set_human_takeover(phone_number, False)
            return False
        return True
    return False

def set_human_takeover(phone_number: str, active: bool) -> None:
    current_status = load_takeover_status()

    if active:
        current_status[phone_number] = {
            "active": True,
            "timestamp": time.time()
        }
    else:
        current_status[phone_number] = {
            "active": False,
            "timestamp": time.time()
        }

    save_takeover_status(current_status)
    log.info(f"🛡️ Takeover {'activado' if active else 'desactivado'} para {phone_number}")

# -----------------------------
# Historial de Conversaciones
# -----------------------------
def get_conversation_history(phone_number: str, max_age_seconds: int = 120) -> List[Dict[str, Any]]:
    filename = sanitize_phone(phone_number) + ".json"
    filepath = os.path.join(CONVERSATION_HISTORY_DIR, filename)

    if os.path.exists(filepath):
        file_age = time.time() - os.path.getmtime(filepath)
        if file_age > max_age_seconds:
            log.warning(f"⚠️ Conversación antigua descartada para {phone_number} ({file_age:.1f} segundos)")
            return []  # Resetear conversación
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log.error(f"❌ Error al decodificar historial de conversación para {phone_number}, iniciando vacío")
            return []
    return []

def add_to_conversation_history(phone_number: str, role: str, content: str) -> List[Dict[str, Any]]:
    history = get_conversation_history(phone_number)

    history.append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })

    # Limita el historial a los últimos 20 mensajes
    if len(history) > 20:
        history = history[-20:]

    filename = sanitize_phone(phone_number) + ".json"
    filepath = os.path.join(CONVERSATION_HISTORY_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        log.info(f"💾 Conversación actualizada para {phone_number}")
    except Exception as e:
        log.error(f"❌ Error al guardar historial para {phone_number}: {e}")

    return history
