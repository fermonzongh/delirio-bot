# Delirio Picante WhatsApp Bot

Este es un bot de WhatsApp para negocios de salsas picantes que utiliza AI para responder preguntas de clientes, acceder a productos desde Google Drive, compartir tu catálogo y permitir atención humana cuando es necesario.

## Características

- Funciona sobre la API oficial de WhatsApp usando Heyoo
- Integra LLM para respuestas inteligentes
- Accede a productos desde una hoja de cálculo en Google Drive
- Comparte automáticamente tu catálogo PDF
- Escala a atención humana cuando el cliente lo solicita
- Guarda el historial de cada conversación
- Permite enviar mensajes manuales como negocio
- API REST para administrar conversaciones
- Webhook seguro con validación de firma

## Estructura del Proyecto

delirio-bot/
* main.py — Punto de entrada FastAPI
* api/
  * routes.py — Webhook y envío manual
  * health.py — Healthcheck avanzado
* core/
  * settings.py — Variables de entorno
* services/
  * conversation.py — Historial y takeover
  * drive.py — Productos desde Google Drive
  * llm_client.py — Lógica de consultas a IA
  * llm_dispatcher.py — Selección de proveedor IA dinámico
  * security.py — Firma de Webhook
  * validators.py — Validaciones de input y seguridad
* models/
  * schemas.py — Modelos de datos Pydantic
* requirements.txt — Dependencias
* .env — Variables sensibles (no subir)

## Instalación

1. Clona el repositorio:

git clone https://github.com/fermonzongh/delirio-bot.git
cd delirio-bot

2. Crea un entorno virtual:

python -m venv venv
source venv/bin/activate  # en Windows: venv\Scripts\activate

3. Instala dependencias:

pip install -r requirements.txt

4. Crea un archivo .env con tus claves:

CLAUDE_API_KEY=tu_api_key_claude
OPENAI_API_KEY=tu_api_key_openai
LLM_PROVIDER=claude  # o openai
PRODUCT_LIST_FILE_ID=tu_id_archivo_drive
CATALOG_PDF_FILE_ID=tu_id_catalogo_drive
HEYOO_TOKEN=tu_token_heyoo
HEYOO_PHONE_ID=tu_id_numero_heyoo
OWNER_PHONE_NUMBER=5491122334455
APP_SECRET=tu_clave_secreta_meta

5. Coloca tu archivo service-account-key.json (clave de Google) en la raíz.

## Configuración de WhatsApp con Heyoo

1. Obtené tu token y phone number ID desde tu administrador de WhatsApp Business API (puede ser Heyoo u otro proveedor).
2. Configura tu webhook:
   - URL: https://tudominio.io/webhook
   - Método: POST
   - Verificación: HolaAI

## Ejecutar el bot localmente

1. Levantá ngrok (si estás local):
ngrok http 8000

2. Iniciá FastAPI:
uvicorn main:app --reload

3. Enviá un mensaje a tu número de WhatsApp desde otro teléfono

## API para administración

Enviar mensaje manual:
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"to": "5491122334455", "message": "Gracias por tu pedido 🔥"}'

Activar atención humana:
curl -X POST http://localhost:8000/takeover \
  -H "Content-Type: application/json" \
  -d '{"customer_phone": "5491122334455", "activate": true}'

Ver conversaciones:
curl http://localhost:8000/conversations

## Licencia

MIT License - ver el archivo LICENSE.
