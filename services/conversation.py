import os
import json
import time
from typing import List, Dict, Any

from core.settings import CONVERSATION_HISTORY_DIR, TAKEOVER_FILE
from core.logger import LoggerManager  # 🚀 Logger agregado

# Instanciar logger
log = LoggerManager(name="conversation", level="INFO", log_to_file=False).get_logger()

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
    active_status = {
        phone: data
        for phone, data in status_dict.items()
        if data.get("active", False)
    }
    try:
        with open(TAKEOVER_FILE, "w", encoding="utf-8") as f:
            json.dump(active_status, f, ensure_ascii=False, indent=2)
        log.info(f"💾 Estado de takeover guardado. Usuarios activos: {len(active_status)}")
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
            "timestamp": time.time(),
            "alerted": False
        }
    else:
        if phone_number in current_status:
            del current_status[phone_number]

    save_takeover_status(current_status)
    log.info(f"🛡️ Takeover {'activado' if active else 'desactivado'} para {phone_number}")

# -----------------------------
# Historial de Conversaciones
# -----------------------------
def _get_conversation_filepath(phone_number: str) -> str:
    filename = sanitize_phone(phone_number) + ".json"
    return os.path.join(CONVERSATION_HISTORY_DIR, filename)

def load_conversation_file(phone_number: str) -> dict:
    filepath = _get_conversation_filepath(phone_number)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"❌ Error al leer conversación para {phone_number}: {e}")
    return {}

def save_conversation_file(phone_number: str, data: dict) -> None:
    filepath = _get_conversation_filepath(phone_number)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"💾 Conversación guardada para {phone_number}")
    except Exception as e:
        log.error(f"❌ Error al guardar conversación para {phone_number}: {e}")

def get_name_from_conversation(phone_number: str) -> str:
    data = load_conversation_file(phone_number)
    if not data:
        return ""

    name = data.get("name", "")
    if not name:
        log.warning(f"⚠️ Nombre no encontrado en conversación para {phone_number}")
    return name

def get_conversation_history(phone_number: str, max_age_seconds: int = 84600) -> List[Dict[str, Any]]:
    data = load_conversation_file(phone_number)

    if not data:
        return []

    last_updated = data.get("last_updated", 0)
    if time.time() - last_updated > max_age_seconds:
        # ⚠️ Conversación vieja, limpiamos historial pero mantenemos el resto
        data["history"] = []
        data["last_updated"] = time.time()
        save_conversation_file(phone_number, data)
        log.warning(f"⚠️ Conversación vieja limpiada para {phone_number}")
        return []

    return data.get("history", [])

def add_to_conversation_history(phone_number: str, role: str, content: str) -> List[Dict[str, Any]]:
    data = load_conversation_file(phone_number)

    if not data:
        data = {
            "phone_number": phone_number,
            "name": "",  # Podemos completarlo después
            "last_updated": time.time(),
            "history": []
        }

    history = data.get("history", [])
    history.append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })

    # Limitar historial
    if len(history) > 20:
        history = history[-20:]

    data["history"] = history
    data["last_updated"] = time.time()

    save_conversation_file(phone_number, data)
    return history

def set_customer_name(phone_number: str, name: str) -> None:
    """Permite guardar el nombre real del usuario cuando se descubre."""
    data = load_conversation_file(phone_number)
    data["name"] = name
    data["last_updated"] = time.time()
    save_conversation_file(phone_number, data)
    log.info(f"👤 Nombre actualizado para {phone_number}: {name}")
