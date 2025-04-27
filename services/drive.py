import os
import io
import json
import time
import pandas as pd
from typing import List, Dict, Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from core.settings import (
    PRODUCT_LIST_FILE_ID,
    CATALOG_PDF_LINK,
    SERVICE_ACCOUNT_FILE,
    PRODUCTS_CACHE_FILE
)
from core.logger import LoggerManager

class DriveService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DriveService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the Drive service with logger and Google Drive client."""
        if self._initialized:
            return
            
        self.log = LoggerManager(name="drive", level="INFO", log_to_file=False).get_logger()
        self._drive_service = None
        self._cache_duration = 86400  # 1 day in seconds
        self._initialized = True
    
    def _get_drive_service(self):
        """Initialize and return the Google Drive service client."""
        if not self._drive_service:
            self.log.info("🔌 Buscando el servicio de Google Drive...")
            SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            self._drive_service = build('drive', 'v3', credentials=credentials)
        return self._drive_service

    def _is_cache_valid(self) -> bool:
        """Check if the cache file exists and is still valid."""
        if not os.path.exists(PRODUCTS_CACHE_FILE):
            self.log.info("📭 Cache no existe aún")
            return False
            
        last_modified = time.time() - os.path.getmtime(PRODUCTS_CACHE_FILE)
        self.log.debug(f"⏱️ Tiempo desde última modificación: {last_modified:.2f} segundos")
        
        return last_modified < self._cache_duration

    def _load_from_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Load products from cache if available and valid."""
        try:
            if self._is_cache_valid():
                with open(PRODUCTS_CACHE_FILE, "r", encoding="utf-8") as f:
                    self.log.info("📦 Cargando productos desde cache local")
                    return json.load(f)
        except Exception as e:
            self.log.error(f"❌ Error al cargar productos de la cache: {e}")
        return None

    def _save_to_cache(self, products: List[Dict[str, Any]]) -> None:
        """Save products to cache file."""
        try:
            with open(PRODUCTS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False)
            self.log.info("💾 Productos guardados en cache")
        except Exception as e:
            self.log.error(f"❌ Error al guardar productos en cache: {e}")

    def _download_file(self) -> io.BytesIO:
        """Download the product list file from Google Drive."""
        service = self._get_drive_service()
        
        self.log.info("📥 [Paso 3] Obteniendo metadatos del archivo...")
        metadata = service.files().get(fileId=PRODUCT_LIST_FILE_ID).execute()
        file_name = metadata.get("name", "")
        self.log.info(f"📄 Nombre del archivo en Drive: {file_name}")

        self.log.info("📥 [Paso 4] Descargando archivo desde Drive...")
        request = service.files().export_media(
            fileId=PRODUCT_LIST_FILE_ID,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        self.log.info("✅ Descarga completa desde Drive")
        file_content.seek(0)
        return file_content

    def load_products(self) -> List[Dict[str, Any]]:
        """Load products from cache or download from Drive if cache is invalid."""
        self.log.info("🔄 [Paso 1] Intentando cargar productos desde caché...")
        
        # Try loading from cache first
        products = self._load_from_cache()
        if products is not None:
            return products

        try:
            # Download and parse file if cache is invalid or missing
            file_content = self._download_file()
            
            self.log.info("📊 [Paso 5] Parseando contenido como Excel...")
            df = pd.read_excel(file_content)
            self.log.info("✅ Archivo leído correctamente como Excel (.xlsx)")
            
            products = df.to_dict("records")
            self.log.info(f"📦 Productos cargados: {len(products)} registros")
            
            # Save to cache for future use
            self._save_to_cache(products)
            
            return products
            
        except Exception as e:
            self.log.error(f"❌ Error al cargar productos desde Drive: {e}")
            raise

    def get_product_info_string(self) -> str:
        """Return formatted product information as a string."""
        products = self.load_products()
        lines = ["INFORMACIÓN DE PRODUCTOS:\n"]

        for product in products:
            try:
                lines.append(f"Nombre: {product.get('Producto', 'Desconocido')}")
                lines.append(f"Precio: ${product.get('Precio', 0):.2f}")
                lines.append(f"Descripción: {product.get('description', 'Sin descripción disponible')}")
                if "heat_level" in product:
                    lines.append(f"Nivel de picante: {product.get('heat_level')}")
                lines.append(f"Stock: {product.get('Stock', 0)}")
                lines.append(f"Tamaño: {product.get('Tamaño', 'Desconocido')}")
                lines.append("")  # línea en blanco
            except Exception as e:
                self.log.error(f"❌ Error procesando un producto: {e}")
                continue

        lines.append(f"📄 CATÁLOGO: {CATALOG_PDF_LINK}\n")
        self.log.info("📚 Información de productos formateada en memoria")
        return "\n".join(lines)

# Create a singleton instance
drive_service = DriveService()
