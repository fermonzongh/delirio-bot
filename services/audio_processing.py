import httpx
import tempfile

from core.settings import HEYOO_TOKEN, OPENAI_API_KEY
from core.logger import LoggerManager

log = LoggerManager(name="audio_processor", level="INFO", log_to_file=False).get_logger()

async def download_audio_from_whatsapp(media_id: str) -> bytes:
    """
    Descarga un audio de WhatsApp API usando el media_id.
    """
    try:
        async with httpx.AsyncClient() as client:
            # 1. Obtener la URL de descarga
            media_response = await client.get(
                f"https://graph.facebook.com/v18.0/{media_id}",
                headers={"Authorization": f"Bearer {HEYOO_TOKEN}"}
            )
            media_response.raise_for_status()
            media_url = media_response.json()["url"]
            log.info(f"🎯 URL de audio obtenida: {media_url}")

            # 2. Descargar el archivo real
            audio_response = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {HEYOO_TOKEN}"}
            )
            audio_response.raise_for_status()
            log.info(f"✅ Audio descargado exitosamente")
            return audio_response.content
    except Exception as e:
        log.error(f"❌ Error descargando audio: {e}")
        return None

async def transcribe_audio_with_whisper(audio_bytes: bytes) -> str:
    """
    Envía un audio a OpenAI Whisper API para obtener la transcripción.
    """
    try:
        # Usamos un archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".ogg") as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio.seek(0)

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {
                    'file': (temp_audio.name, temp_audio.read(), 'audio/ogg')
                }
                data = {
                    'model': 'whisper-1',
                    'response_format': 'text'
                }
                headers = {
                    'Authorization': f"Bearer {OPENAI_API_KEY}"
                }

                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data
                )
                response.raise_for_status()

                transcription = response.text.strip()
                log.info(f"✅ Transcripción recibida")
                return transcription

    except Exception as e:
        log.error(f"❌ Error transcribiendo audio con Whisper: {e}")
        return "No se pudo transcribir el audio."

async def process_audio_message(media_id: str) -> str:
    """
    Flujo completo: descarga el audio, lo transcribe y devuelve el texto.
    """
    audio_data = await download_audio_from_whatsapp(media_id)
    if not audio_data:
        return "No se pudo obtener el audio."

    transcription = await transcribe_audio_with_whisper(audio_data)
    return transcription
