import base64
import httpx
import json
from io import StringIO, BytesIO
import logging
from typing import Any, Dict, List

from docx import Document
from docx.shared import Inches, RGBColor, Mm, Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK

from .local_image_service import local_image_service
from .s3_image_service import s3_image_service
from .repository import Report

logger = logging.getLogger(__name__)

class DocxRenderer:

    def __init__(self):
        self.doc = Document()
        self.logoname = "thermoelectrica_logo.png"
        self.page_height = 29.7
        self.page_width = 21.0
        self.left_margin = 20.4
        self.right_margin = 10
        self.top_margin = 15
        self.bottom_margin = 10
        self.header_distance = 10
        self.footer_distance = 10
        #self.section = self.page_settings()

    @property
    def section(self):
        # доступ к первой секции
        section = self.doc.sections[0]  # доступ к первому разделу
        # высота листа в сантиметрах
        section.page_height = Cm(29.7)
        # ширина листа в сантиметрах
        section.page_width = Cm(21.0)
        # левое поле в миллиметрах
        section.left_margin = Mm(20.4)
        # правое поле в миллиметрах
        section.right_margin = Mm(10)
        # верхнее поле в миллиметрах
        section.top_margin = Mm(15)
        # нижнее поле в миллиметрах
        section.bottom_margin = Mm(10)
        # отступ от верхнего края страницы до 
        # нижнего края нижнего колонтитула
        section.header_distance = Mm(10)
        # отступ от нижнего края страницы до 
        # нижнего края нижнего колонтитула
        section.footer_distance = Mm(10)
        return section


    def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> bytes:
     
        print(f"RENDER DOCX...")
        print(f"RENDER DOCX, REPORT: {report}")
        print(f"RENDER DOCX, PARAMETERS: {parameters}")
        print(f"RENDER DOCX, QUERY RESULTS: {query_results}")

        logo = local_image_service.get_image_data_uri(
            self.logoname, report.path
        )
        # доступ к первой секции
        #section = self.doc.sections[0]  # доступ к первому разделу
  
        # Межстрочный интервал
        style = self.doc.styles['Normal']
        style.paragraph_format.line_spacing = 1.1

        # высота листа в сантиметрах
        #section.page_height = Cm(self.page_height)
        # ширина листа в сантиметрах
        #section.page_width = Cm(self.page_width)
        # левое поле в миллиметрах
        #section.left_margin = Mm(self.left_margin)
        # правое поле в миллиметрах
        #section.right_margin = Mm(self.right_margin)
        # верхнее поле в миллиметрах
        #section.top_margin = Mm(self.top_margin)
        # нижнее поле в миллиметрах
        #section.bottom_margin = Mm(self.bottom_margin)
        # отступ от верхнего края страницы до 
        # нижнего края нижнего колонтитула
        #section.header_distance = Mm(self.header_distance)
        # отступ от нижнего края страницы до 
        # нижнего края нижнего колонтитула
        #section.footer_distance = Mm(self.footer_distance)

        # доступ к верхнему колонтитулу
        header = self.section.header.paragraphs[0]

        # добавляем логотип слева в хедер
        if logo:
            logo_run = header.add_run()
            logo_run.add_picture(BytesIO(base64.b64decode(logo.split(",")[1])), width=Inches(1.5))

        # Добавление текста справа в хедер
        text_run = header.add_run()
        date_format = parameters["period_end"].strftime("«%d» %B %Y г.") if parameters["period_end"] else ""
        text_run.text = f"\t\tПРОТОКОЛ № {parameters['protocol_number']} { parameters['plant_name'] } от { date_format }"
        text_run.font.size = Pt(8)
        #text_run.bold = True
        #text_run.alignment = WD_ALIGN_PARAGRAPH.RIGHT

         # доступ к нижнему колонтитулу
        footer = self.section.footer.paragraphs[0]

        # добавляем нижний колонтитул
        footer.add_run("* согласно РД 34.45-51.300-97 и типовой инструкции по применению термоиндикаторов\t\t")
        footer.style.font.size = Pt(8)
        # выравниваем колонтитул по правому краю
        #footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # добавляем заголовок документа 
        title = self.doc.add_heading(
            (
                f"Протокол теплового контроля контактов и контактных соединений" 
                f" с применением термоиндикаторов на { parameters['plant_name'] }"
            ), 
            1
        ) #.add_break(WD_BREAK.LINE)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # создаем параграф
        p = self.doc.add_paragraph()

        # вставляем пустую строку
        run = p.add_run()
        run.add_break(WD_BREAK.LINE)

        # добавляем номер протокола и название
        p.add_run(
            (
                f"ПРОТОКОЛ № {parameters['protocol_number']} { parameters['plant_name'] } от { date_format }\n"
                f"теплового контроля электрооборудования"
            )
        )
        #run = p.add_run()
        #run.add_break()
        #p.add_run(
            #(
                #f"ПРОТОКОЛ № {parameters['protocol_number']} { parameters['plant_name'] } от { date_format }\n"
                #f"теплового контроля электрооборудования"
            #)
        #)
        #run.font.size = Pt(9)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # вставляем пустую строку
        run = p.add_run()
        run.add_break(WD_BREAK.LINE)

        '''
        <tr>
            <td style="width: 30%; vertical-align: top;">
                <strong>Перечень обследованных электроустановок</strong>
            </td>
            <td style="width: 70%;">
                {% if queries.data %}
                {% set equipment_types = queries.data | map(attribute='equipment_type_name') | unique | list %}
                {% for eq_type in equipment_types %}
                {{ eq_type }}<br>
                {% endfor %}
                {% if queries.inspection_summary %}
                Количество контрольных точек: {{ queries.inspection_summary | sum(attribute='total_point_count') }}<br>
                Количество ТИН: {{ queries.inspection_summary | sum(attribute='total_sticker_count') }}
                {% else %}
                Количество контрольных точек: {{ queries.data | length }}<br>
                Количество ТИН: {{ queries.data | selectattr('is_sticker_present', 'equalto', true) | list | length }}
                {% endif %}
                {% else %}
                Нет данных
                {% endif %}
            </td>
        </tr>
        '''

        # Таблица 1
        table1 = self.doc.add_table(rows=1, cols=2)
        table1.style = 'Table Grid'

        # Установка размеров ячеек Таблицы 1
        table1.autofit = False # Отключает автоматическое выравнивание ширины
        table1.allow_autofit = False # Гарантирует, что Word не переопределит макет
        table1.columns[0].width = Inches(3.0)
        #table1.rows[0].cells[0].width = Inches(3.0)
        table1.columns[1].width = Inches(4.0)
        #table1.rows[0].cells[1].width = Inches(4.0)
    
        # Текст в ячейке 0,0
        #hdr_cells = table1.rows[0].cells
        table1.cell(0,0).text = "Перечень обследованных электроустановок"

        # Размер шрифта в ячейке 0,0
        paragraph = table1.rows[0].cells[0].paragraphs[0]
        #run = paragraph.runs
        font = paragraph.runs[0].font
        font.size= Pt(7.5)
        font.bold = True

        equipment = list(
            set(
                [ item["equipment_type_name"] for item in query_results["data"] ]
            )
        )
        equipment_string = ("\n").join(equipment)

        control_points_count, control_tin_count = 0, 0
        if query_results["inspection_summary"]:
            control_points_count = sum([item["total_point_count"] for item in query_results["inspection_summary"]])
            control_tin_count = sum([item["total_sticker_count"] for item in query_results["inspection_summary"]])
        else:
            control_points_count = len(query_results["data"])
            control_tin_count = sum(
                [
                    1 for item in query_results["data"]
                    if item["is_sticker_present"] is True
                ]
            )

        control_points_string = f"Количество контрольных точек: {control_points_count}"
        control_tin_string = f"Количество ТИН: {control_tin_count}"

        table1.cell(0,1).text = (
            equipment_string + "\n" 
            + control_points_string + "\n" 
            + control_tin_string + "\n"
        )

        # Размер шрифта в ячейке 0,1
        paragraph = table1.rows[0].cells[1].paragraphs[0]
        font = paragraph.runs[0].font
        font.size= Pt(7.5)

        # переход на следующую страницу
        p = self.doc.add_paragraph()
        run = p.add_run()
        run.add_break(WD_BREAK.LINE)

        ### Таблица 3-1 (Заголовки 1) ###
        tab3_columns = 4
        table3 = self.doc.add_table(rows=1, cols=4)
        table3.style = 'Table Grid'

        # Определение цвета фона и текста
        #header_bg = RGBColor(20, 50, 100)  # Тёмно-синий
        #header_text_color = RGBColor(255, 255, 255)  # Белый

        # Установка размеров ячеек Таблицы 3
        table3.autofit = False # Отключает автоматическое выравнивание ширины
        table3.allow_autofit = False # Гарантирует, что Word не переопределит макет
        table3.columns[0].width = Inches(0.5)
        table3.columns[1].width = Inches(1.5)
        table3.columns[2].width = Inches(1.5)
        table3.columns[3].width = Inches(3.5)
        #table3.rows[0].cells[0].width = Inches(0.5)
        #table3.columns[1].width = Inches(4.0)
        #table3.rows[0].cells[1].width = Inches(4.0)

        # Устанавливаем заголовки таблицы
        hdr_cells = table3.rows[0].cells
        hdr_cells[0].text = "№"
        hdr_cells[1].text = "Диспетчерское наименование электрооборудования; узел"
        hdr_cells[2].text = "Фотография термоиндикатора и термограмма"
        hdr_cells[3].text = "Выявленный дефект"

        # Стили шрифта в заголовке Таблицы 3
        paragraph = table3.rows[0].cells[0].paragraphs[0]
        #run = paragraph.runs
        font = paragraph.runs[0].font
        font.size= Pt(7.5)
        font.bold = True

        ### Таблица 3-2 (Заголовок 2) ###
        table3_2 = self.doc.add_table(rows=1, cols=1)
        table3_2.style = 'Table Grid'
        #table3.columns[0].width = Inches(7)
        #hdr_cells = table3.rows[0].cells
        #hdr_cells[0].text = "Аварийные дефекты распределительных устройств"

        ### Таблица 3-3 (Ряды данных) ###
        table3 = self.doc.add_table(rows=0, cols=4)
        table3.style = 'Table Grid'

        # Определение цвета фона и текста
        #header_bg = RGBColor(20, 50, 100)  # Тёмно-синий
        #header_text_color = RGBColor(255, 255, 255)  # Белый

        # Установка размеров ячеек Таблицы 3-3
        table3.columns[0].width = Inches(0.5)
        table3.columns[1].width = Inches(2.5)
        table3.columns[2].width = Inches(1.0)
        table3.columns[3].width = Inches(3.0)

        records = (
            (3, '101', 'Spam'),
            (7, '422', 'Eggs'),
            (4, '631', 'Spam, spam, eggs, and spam')
        )

        for idx, row in enumerate(query_results["data"]):
            group_label = ""
            if row["criticality"] == "CRITICAL" and row["is_panel"] == "MOTOR":
                group_label = "Критические дефекты двигателей"
            elif row["criticality"] == "CRITICAL" and row["is_panel"] == "PANEL":
                group_label = "Критические дефекты распределительных устройств"
            elif row["criticality"] == "EMERGENCY" and row["is_panel"] == "MOTOR":
                group_label = "Аварийные дефекты двигателей"
            elif row["criticality"] == "EMERGENCY" and row["is_panel"] == "PANEL":
                group_label = "Аварийные дефекты распределительных устройств"
            elif row["criticality"] == "DEVELOPING" and row["is_panel"] == "MOTOR":
                group_label = "Развивающиеся дефекты двигателей"
            else:
                group_label = "Развивающиеся дефекты распределительных устройств"
            if group_label:
                table3_2.columns[0].width = Inches(7)
                hdr_cells = table3_2.rows[0].cells
                hdr_cells[0].text = group_label

            row_cells = table3.add_row().cells
            row_cells[0].text = str(idx + 1)
            '''
            {% if row.visual_image_ids %}
                        {% for image_id in row.visual_image_ids %}
                        <div class="image-container">
                            <img src="{{ image_id | image_url }}" alt="{{image_id}}">
                        </div>
                        {% endfor %}
                    {% endif %}
                    {% if row.thermal_image_ids %}
                        {% for image_id in row.thermal_image_ids %}
                        <div class="image-container">
                            <img src="{{ image_id | image_url }}" alt="{{image_id}}">
                        </div>
                        {% endfor %}
                    {% endif %}
                    {% if not row.visual_image_ids and not row.thermal_image_ids %}
                    <em>Изображения отсутствуют</em>
                    {% endif %}
            '''

            image_content = ""
            binary_img = 0
            if row.get("visual_image_id"):
                #for image_id in row["visual_image_id"]:
                #image_path = s3_image_service.image_url(row.get("visual_image_id"))
                #response = httpx.get(image_path)
                #print(f"RESPONSE IMAGE: {response.content}")
                #binary_img = BytesIO(response.content)
                try:
                    image_path = s3_image_service.image_url(row.get("visual_image_id"))
                    response = httpx.get(image_path)
                    binary_img = BytesIO(response.content)
                    #image_path = s3_image_service.image_url(row.get("visual_image_id"))
                    #print(f"VISUAL IMAGE: {row.get('visual_image_id')}")
                    #image_content = self.doc.add_picture(binary_img, width=1.5, height=1.5)
                    #break
                except Exception as e:  #FileNotFoundError
                    print(f"Ошибка получения изображения: {e}")
            if row.get("thermal_image_id"):
                #for image_id in row["thermal_image_id"]:
                #image_path = s3_image_service.image_url(row.get("visual_image_id"))
                #response = httpx.get(image_path)
                #print(f"RESPONSE IMAGE: {response.content}")
                #binary_img = BytesIO(response.content)
                try:
                    image_path = s3_image_service.image_url(row.get("visual_image_id"))
                    response = httpx.get(image_path)
                    binary_img = BytesIO(response.content)
                    #image_path = s3_image_service.image_url(row.get("thermal_image_id"))
                    #print(f"THERMAL IMAGE: {image_id}")
                    #image_content = self.doc.add_picture(binary_img, width=1.5, height=1.5)
                    #break
                except Exception as e:
                    print(f"Ошибка получения изображения: {e}")
            if not row.get("visual_image_id") and not row.get("thermal_image_id"):
                image_content = "Изображения отсутствуют"

            '''
            https://storage.yandexcloud.net/l-inspector-photos/0?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=YCAJEtZoVGGBcZ8ffCdfwOWPY%2F20260528%2Fru-central1%2Fs3%2Faws4_request&X-Amz-Date=20260528T112957Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=eef7d8b6bc111ad31535ac939e5822e2d6e49d6709dfea9f896002e548ed06c5
            https://storage.yandexcloud.net/l-inspector-photos/070bfed2-27ce-4996-9c2e-eee5ff9da477.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=YCAJEtZoVGGBcZ8ffCdfwOWPY%2F20260528%2Fru-central1%2Fs3%2Faws4_request&X-Amz-Date=20260528T113140Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=05a6f7ad8ec82a20bf5e73f2085216e4ee3544d7d26f9bbf489f46e0458d3452
            https://storage.yandexcloud.net/l-inspector-photos/00485fdc-8db2-470d-9e3c-9d1083c06c33.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=YCAJEtZoVGGBcZ8ffCdfwOWPY%2F20260528%2Fru-central1%2Fs3%2Faws4_request&X-Amz-Date=20260528T113140Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=6fdc30860504d8624b5fb18e920f9776efb783b4357b4f65ab478302f50bdee3
            '''

            print(f"RESPONSE IMAGE: {bool(binary_img)}, IDX: {idx}")

            paragraph = row_cells[1].paragraphs[0]
            paragraph.add_run().add_picture(binary_img, width=Inches(2.3))
            #paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            #row_cells[1].text = ""
            row_cells[2].text = ""
            row_cells[3].text = ""

        self.doc.save('demo_report.docx')
        