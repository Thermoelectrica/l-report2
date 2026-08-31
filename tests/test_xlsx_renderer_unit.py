import json
import pytest
from render.services.xlsx_renderer import XlsxRenderer


class TestXlsxRendererUnit:
    """Unit-тесты для XlsxRenderer."""

    # ===================== montage_result =====================
    def test_montage_result(self):
        """Стандартная строка монтажа."""
        assert XlsxRenderer.montage_result(12) == "Термоиндикаторы установлены в количестве 12 шт."

    def test_montage_result_zero(self):
        """Ноль стикеров."""
        assert XlsxRenderer.montage_result(0) == "Термоиндикаторы установлены в количестве 0 шт."

    # ===================== inspection_result =====================
    @pytest.mark.parametrize("protocol, expected_date", [
        ("Протокол №123 от 15.03.2024", "«15» марта 2024 г."),
        ("Протокол №001 от 01.01.2023", "«01» января 2023 г."),
    ])
    def test_inspection_result_success(self, protocol, expected_date):
        """Успешный парсинг протокола — проверка, что дата присутствует."""
        result = XlsxRenderer.inspection_result(protocol)
        assert "Термоиндикаторы функционируют исправно." in result
        assert "протокол №123 от" in protocol.lower() or "протокол №001 от" in protocol.lower()  # проверяем, что protocol корректен
        assert expected_date in result  # проверяем, что дата в строке, а не жёстко сверяем

    def test_inspection_result_invalid_date(self):
        """Неверный формат даты → ValueError."""
        with pytest.raises(ValueError, match="Нарушен формат ввода даты: 32.13.2024"):
            XlsxRenderer.inspection_result("Протокол №1 от 32.13.2024")

    def test_inspection_result_missing_date(self):
        """Отсутствие даты → ValueError."""
        with pytest.raises(ValueError, match="Дата протокола не введена или нарушен формат ввода"):
            XlsxRenderer.inspection_result("Протокол №1")

    # ===================== get_plant_content =====================
    def test_get_plant_content_success(self, tmp_path):
        """Успешный поиск станции."""
        json_file = tmp_path / "plant_reference.json"
        json_content = [
            {
                "plant_name": "Автовская ТЭЦ",
                "montage": {
                    "montage_name": "Монтаж термоиндикаторов",
                    "montage_result": "montage_result"
                },
                "signatories": [{"position": "Инженер", "full_name": "Иванов Иван"}]
            }
        ]
        json_file.write_text(
            json.dumps(json_content, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        renderer = XlsxRenderer()
        name, result, signatories = renderer.get_plant_content(
            "Автовская ТЭЦ", "montage", "12", json_file
        )
        assert name == "Монтаж термоиндикаторов"
        assert result == "Термоиндикаторы установлены в количестве 12 шт."
        assert signatories == [{"position": "Инженер", "full_name": "Иванов Иван"}]

    def test_get_plant_content_not_found(self, tmp_path):
        """Станция не найдена → ValueError."""
        json_file = tmp_path / "plant_reference.json"
        json_file.write_text('[{"plant_name": "Другая ТЭЦ"}]', encoding="utf-8")

        renderer = XlsxRenderer()
        with pytest.raises(ValueError, match="отсутствует в справочниках"):
            renderer.get_plant_content("Неизвестная ТЭЦ", "montage", "12", json_file)

    def test_get_plant_content_missing_control_type(self, tmp_path):
        """Отсутствие control_type в JSON → AttributeError (нужна обработка)."""
        json_file = tmp_path / "plant_reference.json"
        json_content = [
            {
                "plant_name": "Автовская ТЭЦ",
                # "montage" отсутствует
            }
        ]
        json_file.write_text(json.dumps(json_content), encoding="utf-8")

        renderer = XlsxRenderer()
        with pytest.raises(KeyError):
            renderer.get_plant_content("Автовская ТЭЦ", "montage", "12", json_file)

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