"""DOCX_TPL generator for DOCX output."""

import asyncio
import shutil
from datetime import datetime
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Literal
import locale

from PIL import Image
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
import httpx

from .report_renderer import ReportRenderer
from .repository import Report
from .template_renderer import TemplateRenderer, template_renderer
from .s3_image_service import s3_image_service

logger = logging.getLogger(__name__)
locale.setlocale(
    category=locale.LC_ALL,
    locale="Russian"
)


class DocxTplRenderer(ReportRenderer):
    """Generate DOCX using DOCX_TPL from raw data."""

    def __init__(self, template_renderer: TemplateRenderer = template_renderer):
        self.template_renderer = template_renderer
        self.logoname = "thermoelectrica_logo.png"
        self.file_docx = "album_template.docx"
        self.output_path = Path("./generated_template.docx")
        self.resized_images_store = Path("./resized_images_store")
        self.blank_image = "blank_image"
        '''
        if self.resized_images_store.exists():
            shutil.rmtree(self.resized_images_store)
            logger.info(f"Cleaned up resized images directory: {self.resized_images_store}")
        
        # Создаём пустую директорию и два пустых изображения
        self.create_folder(self.resized_images_store)
        '''
    @property
    def format_name(self) -> str:
        return "docxtpl"

    @property
    def file_extension(self) -> str:
        return "docx"
    
    def create_blank_image(self, folder) -> Image:
        """Создать два пустых изображения в новой папке """
        # размер картинок в пикселях и код белого цвета
        for idx, size in enumerate([(506, 680), (506, 380)]):
            image = Image.new("RGB", size, (255, 255, 255))
            image.save(f"{folder}/{self.blank_image}_{idx}.jpg")
            logger.info(f"Created blank image: {folder}/{self.blank_image}_{idx}.jpg")
    
    def create_folder(self, folder: Path) -> None:
        """Создать папку для фотографий """
        if os.path.exists(folder):
            return
        folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created/verified directory for images: {folder.resolve()}")
        self.create_blank_image(folder.resolve())

    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Отрендерить HTML-превью. Возвращает None, если формат не поддерживает превью."""
        return self.template_renderer.render(report, parameters, query_results)

    @property
    def supports_preview(self) -> bool:
        return False
    
    async def fetch_async_data(self, client, item) -> str | bool:
        file_name = str(Path(self.resized_images_store) / item['name'])
        # Если файл уже есть — пропускаем загрузку
        if os.path.isfile(file_name):
            return False

        try:
            async with client.stream(
                "GET",
                item["url"],
                timeout=httpx.Timeout(30.0, connect=10.0, read=20.0),
                follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Записываем в файл
                with open(file_name, "wb") as file:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        file.write(chunk)

                # Изменяем размер изображения
                with Image.open(file_name) as img:
                    width, height = img.size

                    # условие для камер пирометров 
                    # модели FLIR E6xt Wifi (320 x 240) и FLIR E95 (640 x 480)
                    if height in [240, 480]:
                        new_width = 506 # это пиксели для 67мм (72x72 dpi)
                        new_height = int(height * (new_width / width))
                        img = img.resize((new_width, new_height), Image.BICUBIC)
                        img.save(file_name)
                        return True
                    
                    if width > height: # поворот на 90 градусов
                        img = img.rotate(-90, expand=True)
                        width, height = img.size
                    new_height = 680 # это пиксели для 90мм (72x72 dpi)
                    new_width = int(width * (new_height / height))
                    img = img.resize((new_width, new_height), Image.BICUBIC)
                    img.save(file_name)
                return True
                
        except httpx.TimeoutException:
            logger.error(f"Timeout downloading {item['url']}")
            # Удаляем недокачанный файл, чтобы не кэшировался
            if os.path.exists(file_name):
                os.remove(file_name)
            return f"Error: Timeout for {item['name']}"
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {item['url']}")
            return f"Error: HTTP {e.response.status_code} for {item['name']}"
        except Exception as exc:
            logger.exception(f"Failed to download {item['url']}")
            # Удаляем битый файл, чтобы не кэшировался
            if os.path.exists(file_name):
                os.remove(file_name)
            return f"Error: {type(exc).__name__}: {exc}"

    async def fetch_images(self, query_results: Dict[str, List[Dict[str, Any]]]) -> None:
        urls_collection = []
        for row in query_results["data"]:
            image_keys = [ key for key in row.keys() if "image_id" in key ]
            for image in image_keys:
                image_obj = row.get(image)
                if image_obj:
                    if isinstance(image_obj, list):
                        print(f"ROW GET IMAGE: {image_obj}")  # development
                        url = s3_image_service.image_url(image_obj[0])
                    else:
                        url = s3_image_service.image_url(image_obj)
                    urls_collection.append({"name": image_obj, "url": url})

        if not urls_collection:
            return

        async with httpx.AsyncClient() as client:
            tasks = [self.fetch_async_data(client, item) for item in urls_collection]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Подсчёт статистики
            downloaded = sum(1 for r in results if r is True)
            cached = sum(1 for r in results if r is False)
            errors = [r for r in results if isinstance(r, BaseException)]

            logger.info(
                f"Images downloaded: {downloaded}, from cache: {cached}, errors: {len(errors)}"
            )

            if errors:
                error_msg = "Failed to download images:\n" + "\n".join(str(e) for e in errors)
                logger.error(error_msg)
        
    def render_docx(self, report: Report, params: Dict[str, Any]) -> bytes:
        # Проверяем наличие файла DOCX
        docx_file = Path(f"{report.path}/{self.file_docx}")
        if not docx_file.exists():
            raise ValueError(f"Missing {self.file_docx} in {report.path}")
        
        try:
            doc = DocxTemplate(docx_file)
            logo_image = InlineImage(doc, image_descriptor=f"{report.path}/{self.logoname}", width=Mm(40))

            jinja_env = self.template_renderer._create_environment(report) # development
        
            for row in self.query_results["data"]:
                pictures = []
                image_keys = [ key for key in row.keys() if "image_id" in key ]
                for idx, image in enumerate(image_keys):
                    image_obj = row.get(image)
                    if isinstance(image_obj, list): # development
                        image_obj = image_obj[0]
                    if image_obj and os.path.isfile(str(Path(self.resized_images_store) / image_obj)):
                        image_descriptor=f"{self.resized_images_store}/{image_obj}"
                    else:
                        image_descriptor=f"{self.resized_images_store}/{self.blank_image}_{idx}.jpg"
                    picture = InlineImage(
                        doc, 
                        image_descriptor=image_descriptor, 
                        width=Mm(67),
                    )
                    pictures.append(picture)

                print(f"ROW: {row}")  # development
                row["pictures"] = pictures

            context = {
                "params": params,
                "logo_image": logo_image,
                "queries": self.query_results,
                "globals": {
                        "template_name": report.id,
                        "report_name": report.metadata.name,
                        "generated_at": datetime.utcnow().isoformat(),
                        "version": report.metadata.version,
                },
                "page_break": "\f",
            }
            doc.render(context, jinja_env)
            file_stream = io.BytesIO()
            doc.save(file_stream)
            file_stream.seek(0)
        except Exception as exc:
            logger.error(f"DOCX rendering failed: {exc}")
            raise RuntimeError(f"DOCX rendering failed: {exc}")
        return file_stream.getvalue()

    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
        base_url: str | None = None,
    ) -> bytes:
        """
        Takes Args and make DOCX using DOCX_TPL.
        Args:
            report: Report object with template
            parameters: User-provided parameters
            query_results: Query results as DataFrames
            base_url: Base URL for resolving relative paths
        Returns:
            DOCX file content
        """
        self.query_results = query_results

        try:
            logger.info(f"Generating DOCX from raw data (source: {report.path})")

            # If base_url not provided, use report.path as base
            if base_url is None:
                # Convert to absolute path first to avoid "relative paths can't be expressed as file URIs" error
                absolute_path = report.path.resolve()
                base_url = absolute_path.as_uri()

            # создаем папку с resized images если ее нет
            await asyncio.to_thread(self.create_folder, self.resized_images_store)

            # скачиваем изображения
            await self.fetch_images(query_results)

            # рендерим DOCX
            docx_bytes = await asyncio.to_thread(self.render_docx, report, parameters)
            logger.info(f"PDF generated successfully, size: {len(docx_bytes)} bytes")
            return docx_bytes

        except Exception as e:
            logger.error(f"DOCX generation failed: {e}")
            raise RuntimeError(f"DOCX generation failed: {e}")

# Global DocxTplRenderer instance
docxtpl_renderer = DocxTplRenderer()
