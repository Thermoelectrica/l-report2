"""Xlsx generator for xlsx output."""

import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, List

from tempfile import NamedTemporaryFile
from openpyxl import Workbook
from openpyxl.styles import NamedStyle, Font, Border, Side, Alignment
from openpyxl.utils import get_column_letter

from .report_renderer import ReportRenderer
from .repository import Report
from .template_renderer import template_renderer

logger = logging.getLogger(__name__)

class XlsxWorkControl(ReportRenderer):
    """Generate XLSX using Xlsx from raw data."""

    def __init__(self):
        self.exclude_names = (
            "Попов Алексей Андреевич",
            "Cкребцов Станислав Юрьевич",
            "Алексей Валерьевич Лесив",
            "Test Inspector",
            "Евлампия Иннокеньтевна",
            "Бирюков Арсений Андреевич",
            "Гришин Егор Витальевич",
            "Иванов Иван Иванович",
            "Годовалов Владимир Алексеевич",
            "Андреев Денис Альбертович",
            "Сорванова Ксения Владимировна",
            "Инспектор КС ГЭС",
            "Инспектор экскаваторы",
            "Инспектор Карелия",
            "Ерошкина Елизавета Алексеевна",
            "Демо"
        )
        # Первое значение - название столбца
        # Второе значение - ширина столбца
        # Третье значение - имя ключа из self.summary_analytics
        # или пропуск ("") или обособленная операция
        self.header_analitycs = (
            ("№ п/п", 10, ""),
            ("Ф.И.О.", 40, ""),
            ("Роль", 20, "Роль:"),
            ("Ко-во рабочих дней", 20, "Сумма дней"),
            ("Среднее время в день, ч.", 20, "Время:"),
            ("Общее кол-во установленных ТИ, шт.", 20, "ТИ (шт.):"),
            ("Просроченные отчеты", 20, ""),
            ("Кол-во ошибок", 20, ""),
            ("Объекты", 40, "Объект:")
        )
        self.WEEKDAYS = {
            0: 'пн', 1: 'вт', 2: 'ср', 3: 'чт',
            4: 'пт', 5: 'сб', 6: 'вс'
        }
        
    @property
    def format_name(self) -> str:
        return "xlsx-work"

    @property
    def file_extension(self) -> str:
        return "xlsx"

    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Отрендерить HTML-превью. Возвращает None, если формат не поддерживает превью."""
        return template_renderer.render(report, parameters, query_results)

    @property
    def supports_preview(self) -> bool:
        return False

    def cell_calculator(self, key: str, obj: dict[str, list[str]]) -> str:
        """Вычисляет значение ячейки для аналитической справки по ключу."""
        if key == "Роль:":
            unique = list(set(obj[key]))
            if not unique:
                return ""
            if len(unique) == 1:
                return unique[0]
            return f"{unique[0]}/{unique[1]}"
        if key == "Сумма дней":
            times = obj.get("Время:") or []
            return len(times)
        if key == "Время:":
            times = obj.get("Время:") or []
            if not times:
                return "00:00"
            return self.average_time(times)
        if key == "ТИ (шт.):":
            values = obj.get("ТИ (шт.):") or []
            return str(sum(int(i) for i in values if i))
        if key == "Объект:":
            plants = list(set(obj.get("Объект:") or []))
            if len(plants) > 1:
                return ", ".join(plants)
            return plants[0] if plants else ""
        return ""

    def average_time(self, times: list[str]) -> str:
        """Вычисляет среднее время из списка строк в формате HH:MM."""
        minutes = sum(
            int(t.split(":")[0]) * 60 + int(t.split(":")[1])
            for t in times
        )
        avg_minutes = minutes // len(times)
        hh, mm = divmod(avg_minutes, 60)
        return f"{hh:02d}:{mm:02d}"

    def time_converter(self, hours: float | None) -> str:
        """Конвертирует часы в строку формата HH:MM."""
        if hours is None:
            return "0"
        hh, mm = divmod(int(hours * 60), 60)
        return f"{hh:02d}:{mm:02d}"

    def get_value(
        self, 
        col_data: dict | None = None, 
        idx: int | None = None,
        role: str | None = None
    ) -> tuple[int, list[list[str]]]:
        """Формирует структуру данных для ячеек отчета."""
        enable = (
            col_data is not None
            and role is not None
            and idx is not None
            and col_data.get("work_hours")
            and col_data["work_hours"][0] is not None
        )
        plant = col_data['plant_name'][idx] if enable else None
        stickers = col_data['montage'][idx] if enable else None
        hours = col_data['work_hours'][idx] if enable else 0
        percentage = col_data['work_percentage'][idx] if enable else 0
        montage = hours * percentage / 100 if enable else 0
        review = hours * (1 - percentage / 100) if enable else 0
        value = [
            ["Объект:", f"{plant}"],
            ["Роль:", f"{role}"],
            ["ТИ (шт.):", f"{stickers or 0}"],
            ["Дефекты:", ""],
            ["Время:", self.time_converter(hours)],
            ["Монтаж:", self.time_converter(montage)],
            ["Осмотр:", self.time_converter(review)],
            ["Тех.акт:", ""],
            ["Сдан:", ""],
            ["Протокол:", ""],
            ["Сдан:", ""],
            ["Проверено:", ""],
            ["Ошибки:", ""],
        ]
        return len(value), value

    def fill_summary_analytics(self, full_name: str, value: list[str], col_idx: int) -> None:
        """Накапливает данные для аналитической справки по инспектору."""
        if col_idx % 2 == 0:
            if self.summary_analytics.get(full_name):
                if self.summary_analytics[full_name].get(value[0]):
                    self.summary_analytics[full_name][value[0]].append(value[1])
                else:
                    self.summary_analytics[full_name].update({value[0]: [value[1]]})
            else:
                self.summary_analytics[full_name] = {}
                self.summary_analytics[full_name].update({value[0]: [value[1]]})

    def render_xlsx(self, report: Report, params: Dict[str, Any]) -> bytes:
        """Генерирует XLSX с фактическим учетом работы и аналитической справкой."""
        
        if not self.query_results.get("data"):
            raise ValueError("Нет данных для формирования документа в указанный период")

        self.summary_analytics = {}

        try:
            # Открываем шаблон
            wb = Workbook()
            # Удаляем лист по умолчанию
            wb.remove(wb.active)
            # Создаем первый лист
            wb.create_sheet("Фактический учет работы")
            # Получаем первый лист
            sheet = wb["Фактический учет работы"]
            
            # Задаем стили
            sd = Side(style="thin")
            border=Border(left=sd, top=sd, right=sd, bottom=sd)
            font=Font(name="Times New Roman", bold=False, size=14, italic=False)
            bold_font=Font(name="Times New Roman", bold=True, size=14, italic=False)
            alignment=Alignment(
                wrap_text=True,
                horizontal="left",
                vertical="center",
            )
            base_cell = NamedStyle(
                name="base_cell", 
                font=font,
                alignment=Alignment(
                    wrap_text=True, 
                    horizontal="center", 
                    vertical="center",
                ),
            )
            table_cell = NamedStyle(
                name="table_cell", 
                font=font,
                alignment=alignment,
                border=border
            )
            notice_cell = NamedStyle(
                name="notice_cell",
                font=Font(
                    name="Times New Roman", 
                    bold=True, 
                    size=14, 
                    italic=False, 
                )
            )

            # Регистрируем стили
            for style in (base_cell, table_cell, notice_cell):
                if style.name not in wb.named_styles:
                    wb.add_named_style(style)

            # Заголовок документа
            cell = sheet.cell(
                row=1, 
                column=5, 
                value=f"УЧЕТ ВРЕМЕНИ № {params['act_number']}"
            )
            cell.style = notice_cell

            # Дата формирования акта
            cell = sheet.cell(
                row=2, 
                column=1, 
                value=(
                    f"Интервал отчета: {params['period_start'].strftime('%d.%m.%Y')} - "
                    f"{params['period_end'].strftime('%d.%m.%Y')}"
                )
            )
            cell.style = base_cell
            cell.alignment = Alignment(horizontal="left")
            sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=4)

            sheet.append([None] * sheet.max_column)

            # Задаем шапку таблицы для трех колонок
            for idx, data in enumerate(["№", "ФИО", "Должность"], start=1):
                cell = sheet.cell(
                    row = sheet.max_row, 
                    column = idx, 
                    value = data
                )
                cell.style = table_cell
                cell.font = bold_font
                cell.alignment = Alignment(horizontal="center")

            # Задваиваем каждый элемент
            doubled = [
                item for item in self.query_results["data"]
                for _ in range(2)
            ]

            # Задаем шапку таблицы для остальных колонок
            for idx, data in enumerate(doubled, start=4):
                cell = sheet.cell(
                    row = sheet.max_row, 
                    column = idx, 
                    value = f"{(data['day'] + timedelta(days=1)).strftime('%d.%m.%Y')}"
                )
                cell.style=table_cell
                cell.font = bold_font
                cell.alignment = Alignment(horizontal="center")

            # Объединяем по 2 ячейки в шапке
            last_row = sheet.max_row
            for col in range(4, len(doubled) + 4, 2):
                left = get_column_letter(col)
                right = get_column_letter(col + 1)
                sheet.merge_cells(f"{left}{last_row}:{right}{last_row}")

            # Определяем стартовую строку
            start_row = sheet.max_row + 1

            extended_data = [{}, {}, {}]
            extended_data.extend(doubled)

            # Задаем ширину ячеек
            max_cols = len(extended_data)
            for i in range(2, max_cols + 1):
                col_letter = get_column_letter(i)
                sheet.column_dimensions[col_letter].width = 25
            sheet.column_dimensions["A"].width = 10

            # Получаем количество ячеек отчета 
            repeat, _ = self.get_value()

            rep_inspectors = [
                x for x in self.query_results["inspectors"]
                if x["full_name"] not in self.exclude_names
                for _ in range(repeat)
            ]

            # Формируем таблицу Учет работы
            counter = 0
            merge_dict = {}
            for row_idx, row_data in enumerate(rep_inspectors, start=start_row):
                if (counter == repeat):
                    counter = 0
                current_row = row_idx - start_row + 1
                # Заполняем строку: индекс row_idx соответствует next row
                for col_idx, col_data in enumerate(extended_data, start=1):
                    # установка значений
                    if col_idx == 1:
                        cell_obj = sheet.cell(row=row_idx, column=col_idx, value=(current_row))
                    if col_idx == 2:
                        cell_obj = sheet.cell(row=row_idx, column=col_idx, value=row_data["full_name"])
                        if merge_dict.get(row_data["full_name"]):
                            merge_dict[row_data["full_name"]].append(row_idx)
                        else:
                            merge_dict[row_data["full_name"]] = [row_idx]
                    if col_idx == 3:
                        position = row_data.get("position", "Инженер теплового контроля")
                        cell_obj = sheet.cell(row=row_idx, column=col_idx, value=position)
                    if col_idx > 3:
                        try:
                            idx_major = col_data["full_name_major"].index(row_data["full_name"])
                            _, value = self.get_value(col_data, idx_major, "РР")
                            pos = 0
                            if col_data == extended_data[col_idx -2]:
                                pos = 1
                            cell_obj = sheet.cell(
                                row=row_idx, 
                                column=col_idx, 
                                value=value[counter][pos]
                            )
                            self.fill_summary_analytics(row_data["full_name"], value[counter], col_idx)
                        except ValueError:
                            success = False
                            for idx, elem in enumerate(col_data["full_names_minor"]):
                                try:
                                    _ = elem.index(row_data["full_name"])
                                    _, value = self.get_value(col_data, idx, "ПР")
                                    pos = 0
                                    if col_data == extended_data[col_idx -2]:
                                        pos = 1
                                    cell_obj = sheet.cell(
                                        row=row_idx, 
                                        column=col_idx, 
                                        value=value[counter][pos]
                                    )
                                    self.fill_summary_analytics(row_data["full_name"], value[counter], col_idx)
                                    success = True
                                    break
                                except ValueError:
                                    continue
                            if not success:
                                cell_obj = sheet.cell(row=row_idx, column=col_idx, value="")
                    # установка стилей
                    cell_obj.style=table_cell
                    cell_obj.alignment=Alignment(horizontal="center", vertical="center", wrap_text=True)
                    if col_idx > 3 and col_idx % 2 == 0 :
                        cell_obj.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                counter += 1

            # схлопываем ряды колонок A, B, C
            for idx, val in enumerate(merge_dict.values(), start=1):
                val_min = min(val)
                val_max = max(val)
                sheet.cell(row=val_min, column=1, value=idx)
                for letter in ["A", "B", "C"]:
                    sheet.merge_cells(
                        f"{letter}{val_min}:{letter}{val_max}"
                    )

            # фиксируем колонки A, B, C
            sheet.freeze_panes = 'D1'
            
            # Добавляем пустую строку
            sheet.append([None] * sheet.max_column)

            # Начинаем делать аналитическую справку
            wb.create_sheet("Аналитическая справка")
            sheet1 = wb["Аналитическая справка"]

            # Заголовок документа
            cell = sheet1.cell(
                row=1, 
                column=4, 
                value="Аналитическая справка"
            )
            cell.style = notice_cell
            dts = params["period_start"]
            dte = params["period_end"]
            cell = sheet1.cell(
                row=2, 
                column=3, 
                value=(
                    "еженедельного выполнения работ за период с "
                    f"{dts.strftime('%d.%m.%Y')} ({self.WEEKDAYS[dts.weekday()]}) по "
                    f"{dte.strftime('%d.%m.%Y')} ({self.WEEKDAYS[dte.weekday()]})"
                )
            )
            cell.style = notice_cell
            
            header_row = sheet1.max_row + 2

            # Задаем шапку таблицы
            for idx, data in enumerate(self.header_analitycs, start=1):
                cell = sheet1.cell(
                    row = header_row, 
                    column = idx, 
                    value = data[0]
                )
                cell.style = table_cell
                cell.font = bold_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Задаем ширину ячеек
            max_cols = len(self.header_analitycs)
            for i in range(1, max_cols + 1):
                col_letter = get_column_letter(i)
                sheet1.column_dimensions[col_letter].width = self.header_analitycs[i - 1][1]

            # Формируем таблицу Аналитическая справка
            start_row = sheet1.max_row + 1
            for key, value in self.summary_analytics.items():
                for idx, item in enumerate(self.header_analitycs, start=1):
                    if idx == 1:
                        cell_obj = sheet1.cell(row=start_row, column=idx, value=(start_row - header_row))
                    if idx == 2:
                        cell_obj = sheet1.cell(row=start_row, column=idx, value=key)
                    if idx > 2:
                        cell_data =  self.cell_calculator(item[2], value)
                        cell_obj = sheet1.cell(row=start_row, column=idx, value=cell_data)
                    cell_obj.style = table_cell
                    cell_obj.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                start_row += 1
              
            # Сохраняем изменения
            with NamedTemporaryFile() as tmp:
                wb.save(tmp.name)
                tmp.seek(0)
                file_stream = tmp.read()

        except Exception as exc:
            logger.error(f"XLSX-work rendering failed: {exc}")
            raise RuntimeError(f"XLSX-work rendering failed: {exc}")
        return file_stream

    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
        base_url: str | None = None,
    ) -> bytes:
        """
        Takes Args and make XLSX using XLSX.
        Args:
            report: Report object with template
            parameters: User-provided parameters
            query_results: Query results as DataFrames
            base_url: Base URL for resolving relative paths
        Returns:
            XLSX file content
        """
        self.query_results = query_results

        try:
            logger.info(f"Generating XLSX-work from raw data (source: {report.path})")

            # If base_url not provided, use report.path as base
            if base_url is None:
                # Convert to absolute path first to avoid "relative paths can't be expressed as file URIs" error
                absolute_path = report.path.resolve()
                base_url = absolute_path.as_uri()

            # рендерим XLSX
            xlsx_bytes = await asyncio.to_thread(self.render_xlsx, report, parameters)
            logger.info(f"XLSX-work generated successfully, size: {len(xlsx_bytes)} bytes")
            return xlsx_bytes

        except Exception as e:
            logger.error(f"XLSX-work generation failed: {e}")
            raise RuntimeError(f"XLSX-work generation failed: {e}")

# Global XlsxRenderer instance
xlsx_work_control = XlsxWorkControl()
