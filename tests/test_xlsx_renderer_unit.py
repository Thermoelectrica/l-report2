import pytest
from render.services.xlsx_renderer import XlsxRenderer


class TestXlsxRendererUnit:
    """Unit-тесты для XlsxRenderer."""

    # ===================== montage_result =====================
    def test_montage_result(self):
        """Стандартная строка монтажа."""
        assert "Термоиндикаторы установлены в количестве 12 шт." in XlsxRenderer.montage_result(12)

    def test_montage_result_zero(self):
        """Ноль стикеров."""
        assert "Термоиндикаторы установлены в количестве 0 шт." in XlsxRenderer.montage_result(0)

    # ===================== inspection_result =====================
    @pytest.mark.parametrize("protocol, expected_date", [
        ("Протокол №123 от 15.03.2024", "«15» марта 2024 г."),
        ("Протокол №001 от 01.01.2023", "«01» января 2023 г."),
    ])
    def test_inspection_result_success(self, protocol, expected_date):
        """Успешный парсинг протокола — проверка, что дата присутствует."""
        result = XlsxRenderer.inspection_result(protocol)
        assert "Термоиндикаторы функционируют исправно." in result
        assert "протокол №123 от" in protocol.lower() or "протокол №001 от" in protocol.lower()
        assert expected_date in result

    def test_inspection_result_invalid_date(self):
        """Неверный формат даты → ValueError."""
        with pytest.raises(ValueError, match="Нарушен формат ввода даты: 32.13.2024"):
            XlsxRenderer.inspection_result("Протокол №1 от 32.13.2024")

    def test_inspection_result_missing_date(self):
        """Отсутствие даты → ValueError."""
        with pytest.raises(ValueError, match="Дата протокола не введена или нарушен формат ввода"):
            XlsxRenderer.inspection_result("Протокол №1")

    # ===================== get_plant_content =====================
    def test_get_plant_content_success(self):
        """Успешный поиск станции."""
        plant_data = [
            {
                "plant_name": "Автовская ТЭЦ",
                "montage": {
                    "montage_name": "Монтаж термоиндикаторов",
                    "montage_result": "montage_result"
                },
                "signatories": [{"position": "Инженер", "full_name": "Иванов Иван"}]
            }
        ]

        renderer = XlsxRenderer()
        name, result, signatories = renderer.get_plant_content(
            {"plant_name": "Автовская ТЭЦ", "protocol_number": "12"},
            "montage",
            {"montage": 12},
            plant_data,
        )
        assert name == "Монтаж термоиндикаторов"
        assert result == "Термоиндикаторы установлены в количестве 12 шт."
        assert signatories == [{"position": "Инженер", "full_name": "Иванов Иван"}]

    def test_get_plant_content_not_found(self):
        """Станция не найдена → ValueError."""
        plant_data = [{"plant_name": "Другая ТЭЦ"}]

        renderer = XlsxRenderer()
        with pytest.raises(ValueError, match="Станция"):
            renderer.get_plant_content(
                {"plant_name": "Неизвестная ТЭЦ", "protocol_number": "12"},
                "montage",
                {"montage": 12},
                plant_data,
            )

    def test_get_plant_content_missing_control_type(self):
        """Отсутствие control_type в JSON → ValueError."""
        plant_data = [
            {
                "plant_name": "Автовская ТЭЦ",
                # "montage" отсутствует
            }
        ]

        renderer = XlsxRenderer()
        with pytest.raises(ValueError, match="Станция"):
            renderer.get_plant_content(
                {"plant_name": "Автовская ТЭЦ", "protocol_number": "12"},
                "montage",
                {"montage": 12},
                plant_data,
            )

    # ===================== supports_preview =====================
    def test_supports_preview_false(self):
        """Поддержка превью — False (как в коде)."""
        renderer = XlsxRenderer()
        assert renderer.supports_preview is False

    def test_format_name_and_extension(self):
        """Название формата и расширения."""
        renderer = XlsxRenderer()
        assert renderer.format_name == "xlsx"
        assert renderer.file_extension == "xlsx"
