import os
import io
import json
import time
import pandas as pd

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from core.settings import (
    PRODUCT_LIST_FILE_ID,
    CATALOG_PDF_LINK,
    SERVICE_ACCOUNT_FILE,
    PRODUCTS_CACHE_FILE
)
from core.logger import LoggerManager  # 🚀 Logger agregado

# Instanciar logger
log = LoggerManager(name="drive", level="DEBUG", log_to_file=False).get_logger()

# Inicializa el cliente de Google Drive
def get_drive_service():
    log.info("🔌 Buscando el servicio de Google Drive...")
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    return build('drive', 'v3', credentials=credentials)

# Carga el archivo de productos y lo cachea
def load_products_from_drive():
    log.info("🔄 [Paso 1] Intentando cargar productos desde caché...")

    try:
        if os.path.exists(PRODUCTS_CACHE_FILE):
            log.info("✅ Cache encontrada")
            last_modified = time.time() - os.path.getmtime(PRODUCTS_CACHE_FILE)
            log.debug(f"⏱️ Tiempo desde última modificación: {last_modified:.2f} segundos")

            if last_modified < 3600:
                with open(PRODUCTS_CACHE_FILE, "r", encoding="utf-8") as f:
                    log.info("📦 Cargando productos desde cache local")
                    try:
                        return json.load(f)
                    except Exception as e:
                        log.error(f"❌ Error al cargar productos de la cache: {e}")
            else:
                log.warning("⚠️ Cache vencida (más de 1 hora)")
        else:
            log.info("📭 Cache no existe aún")
    except Exception as e:
        log.error(f"❌ Error al leer la cache: {e}")

    log.info("🔌 [Paso 2] Obteniendo cliente de Google Drive...")
    try:
        service = get_drive_service()
        log.info("✅ Cliente de Google Drive inicializado")
    except Exception as e:
        log.error(f"❌ Error al inicializar cliente de Drive: {e}")
        raise

    try:
        log.info("📥 [Paso 3] Obteniendo metadatos del archivo...")
        metadata = service.files().get(fileId=PRODUCT_LIST_FILE_ID).execute()
        file_name = metadata.get("name", "")
        log.info(f"📄 Nombre del archivo en Drive: {file_name}")
    except Exception as e:
        log.error(f"❌ Error al obtener metadatos del archivo: {e}")
        raise

    try:
        log.info("📥 [Paso 4] Descargando archivo desde Drive...")
        request = service.files().export_media(
            fileId=PRODUCT_LIST_FILE_ID,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()
        log.info("✅ Descarga completa desde Drive")
    except Exception as e:
        log.error(f"❌ Error durante la descarga del archivo: {e}")
        raise

    file_content.seek(0)

    try:
        log.info("📊 [Paso 5] Parseando contenido como Excel...")
        df = pd.read_excel(file_content)
        log.info("✅ Archivo leído correctamente como Excel (.xlsx)")
    except Exception as e:
        log.error(f"❌ Error al leer el archivo como Excel: {e}")
        raise

    products = df.to_dict("records")
    log.info(f"📦 Productos cargados: {len(products)} registros")

    try:
        with open(PRODUCTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False)
        log.info("💾 Productos guardados en cache")
    except Exception as e:
        log.error(f"❌ Error al guardar productos en cache: {e}")

    return products

# Devuelve los productos como texto formateado para Claude
def get_product_info_string():
    products = load_products_from_drive()
    lines = ["INFORMACIÓN DE PRODUCTOS:\n"]

    for product in products:
        try:
            lines.append(f"Nombre: {product.get('Producto', 'Desconocido')}")
            lines.append(f"Precio: ${product.get('Precio', 0):.2f}")
            lines.append(f"Descripción: {product.get('description', 'Sin descripción disponible')}")
            if "heat_level" in product:
                lines.append(f"Nivel de picante: {product.get('heat_level')}")
            lines.append(f"Stock: {product.get('Stock', 0)}")
            lines.append("")  # línea en blanco
        except Exception as e:
            log.error(f"❌ Error procesando un producto: {e}")
            continue

    lines.append(f"📄 CATÁLOGO: {CATALOG_PDF_LINK}\n")
    log.info("📚 Información de productos formateada en memoria")
    return "\n".join(lines)
