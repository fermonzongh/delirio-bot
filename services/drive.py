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

# Inicializa el cliente de Google Drive
def get_drive_service():
    print("buscando el servicio")
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    
    return build('drive', 'v3', credentials=credentials)

# Carga el archivo de productos y lo cachea
def load_products_from_drive():
    print("🔄 [Paso 1] Intentando cargar desde caché...")

    try:
        if os.path.exists(PRODUCTS_CACHE_FILE):
            print("✅ Cache encontrada")
            last_modified = time.time() - os.path.getmtime(PRODUCTS_CACHE_FILE)
            print(f"⏱️ Tiempo desde última modificación: {last_modified:.2f} segundos")

            if last_modified < 3600:
                with open(PRODUCTS_CACHE_FILE, "r",  encoding="utf-8") as f:
                    print("📦 Cargando productos desde caché local")
                    try:
                        return json.load(f)
                    except Exception as e:
                        print("Error de carga de cache: ", e)
            else:
                print("⚠️ Cache vencida (más de 1 hora)")
        else:
            print("📭 Cache no existe aún")
    except Exception as e:
        print(f"❌ Error al leer la cache: {e}")

    print("🔌 [Paso 2] Obteniendo cliente de Google Drive...")
    try:
        service = get_drive_service()
        print("✅ Cliente de Google Drive inicializado")
    except Exception as e:
        print(f"❌ Error al inicializar cliente de Drive: {e}")
        raise

    try:
        print("📥 [Paso 3] Obteniendo metadatos del archivo...")
        metadata = service.files().get(fileId=PRODUCT_LIST_FILE_ID).execute()
        file_name = metadata.get("name", "")
        print(f"📄 Nombre del archivo en Drive: {file_name}")
    except Exception as e:
        print(f"❌ Error al obtener metadatos del archivo: {e}")
        raise

    try:
        print("📥 [Paso 4] Descargando archivo desde Drive...")
        request = service.files().export_media(
            fileId=PRODUCT_LIST_FILE_ID,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()
        print("✅ Descarga completa")
    except Exception as e:
        print(f"❌ Error durante la descarga del archivo: {e}")
        raise

    file_content.seek(0)

    try:
        print("📊 [Paso 5] Parseando contenido exportado desde Google Sheets como Excel...")
        df = pd.read_excel(file_content)  # Forzamos formato conocido
        print("✅ Archivo leído correctamente como Excel (.xlsx)")
    except Exception as e:
        print(f"❌ Error al leer el archivo como Excel: {e}")
        raise

    products = df.to_dict("records")
    print(f"📦 Productos cargados: {len(products)}")

    try:
        with open(PRODUCTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False)
        print("💾 Productos guardados en cache")
    except Exception as e:
        print(f"❌ Error al guardar productos en cache: {e}")

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
        except:
            continue

    lines.append(f"📄 CATÁLOGO: {CATALOG_PDF_LINK}\n")
    print("Informacion en memoria")
    return "\n".join(lines)
