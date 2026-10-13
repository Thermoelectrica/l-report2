# test_template_renderer.py
from jinja2 import Environment
import pytest
from unittest.mock import Mock
from datetime import datetime
from render.services.template_renderer import TemplateRenderer, Report


class TestTemplateRenderer:
    def test_template_file_exists(self, tmp_path):
        # Arrange
        renderer = TemplateRenderer()
        report = Mock(spec=Report)
        report.path = str(tmp_path)
        
        # Создаём фейковый шаблон
        template_file = tmp_path / "index.html.j2"
        template_file.write_text("Hello {{ name }}")

        try:
            env = renderer._create_environment(report)
            assert isinstance(env, Environment)
            # Проверим, что действительно загрузчик найдёт шаблон
            assert env.get_template("index.html.j2")
        except Exception as e:
            pytest.fail(f"_create_environment raised unexpected exception: {e}")

    def test_missing_template_raises_error(self, tmp_path):
        # Arrange
        renderer = TemplateRenderer()
        report = Mock(spec=Report)
        report.path = str(tmp_path)

        with pytest.raises(ValueError, match="Missing index.html.j2 in"):
            renderer._create_environment(report)

    # ─── history_inspection_parser ──────────────────────────────────────

    def _make_row(self, **overrides):
        """Создаёт стандартный row с дефолтными значениями."""
        base = {
            "unit_name": "РУ-0,4 кВ",
            "history_unit_names": ["РУ-0,4 кВ", "Щит-1"],
            "history_unit_detected_at": [datetime(2026, 1, 15), datetime(2026, 2, 10)],
            "history_t_observed": [45.0, 50.0],
            "history_t_stickers": [">100", "80"],
            "history_t_excess": [10.0, 12.0],
            "history_t_environment": [20.0, 22.0],
            "defect_status": "DETECTED",
            "started_at": datetime(2026, 9, 1),
            "t_sticker": ">120",
            "t_observed": 55.0,
            "t_environment": 20.0,
            "t_excess": 15.0,
        }
        base.update(overrides)
        return base

    renderer = TemplateRenderer()

    # 1. unit_name не найден в истории → ValueError
    def test_raises_value_error_when_unit_not_found(self):
        row = self._make_row(unit_name="Не существует")
        with pytest.raises(ValueError, match="not in the list"):
            self.renderer.history_inspection_parser(row)

    # 2. defect_status == RESOLVED → "дефект устранен"
    def test_returns_resolved_message(self):
        row = self._make_row(defect_status="RESOLVED")
        result = self.renderer.history_inspection_parser(row)
        assert "дефект устранен" in result
        assert "регистрация дефекта" in result
        # Проверяем, что есть разделение \n\n
        parts = result.split("\n\n")
        assert len(parts) == 2

    # 3. Условие 1: рост абсолютной температуры > 10
    def test_returns_dev_grow_absolute_when_t_max_differs_over_10(self):
        # history_t_max = max(100, 45) = 100
        # t_max = max(120, 55) = 120
        # 120 - 100 = 20 > 10 → срабатывает cond_one
        row = self._make_row(
            t_sticker=">120",
            t_observed=55.0,
            history_t_observed=[45.0],
            history_t_stickers=[">100"],
        )
        result = self.renderer.history_inspection_parser(row)
        assert "развитие дефекта" in result
        assert "рост абсолютного значения" in result

    # 4. Условие 2: нет истории t_observed, рост t_sticker > 10
    def test_returns_dev_grow_sticker_when_no_history_observed(self):
        # history_t_observed = 0 (пустой список), history_t_sticker = 80
        # t_sticker = 120, t_observed = 0
        # 120 - 80 = 40 > 10 → срабатывает cond_two
        row = self._make_row(
            history_t_observed=[],
            history_t_stickers=["80"],
            t_sticker=">120",
            t_observed=0,
        )
        result = self.renderer.history_inspection_parser(row)
        assert "развитие дефекта" in result
        assert "Ттин" in result

    # 5. По умолчанию: defect не устранён (ни одно условие не срабатывает)
    def test_returns_not_resolved_by_default(self):
        # t_max = max(50, 30) = 50, history_t_max = max(40, 25) = 40
        # 50 - 40 = 10, НЕ > 10 → cond_one не срабатывает
        row = self._make_row(
            t_sticker=">50",
            t_observed=30.0,
            history_t_observed=[25.0],
            history_t_stickers=[">40"],
        )
        result = self.renderer.history_inspection_parser(row)
        assert "дефект не устранен" in result

    # 6. Условие 3: рост превышения (delta_t) > 10
    def test_returns_dev_grow_excess_when_delta_differs_over_10_false(self):
        # Переопределяем t_sticker чтобы cond_one не сработал
        # history_delta_t = 45 - 20 - 10 = 15
        # delta_t = 55 - 20 - 15 = 20
        # 20 - 15 = 5 < 10 → cond_three НЕ срабатывает
        row = self._make_row(
            t_sticker=">50",
            t_observed=55.0,
            history_t_observed=[45.0],
            history_t_stickers=[">40"],
            history_t_excess=[10.0],
            history_t_environment=[20.0],
            t_excess=15.0,
        )
        result = self.renderer.history_inspection_parser(row)
        assert "дефект не устранен" in result

    # 7. Рост превышения > 10 → срабатывает cond_three
    def test_returns_dev_grow_excess_when_delta_differs_over_10_true(self):
        # history_t_observed=30, t_observed=60 → cond_two пропускается (оба truthy)
        # t_max = max(50, 60) = 60, history_t_max = max(80, 30) = 80
        # 60 - 80 = -20, НЕ > 10 → cond_one пропускается
        # history_delta_t = 30 - 20 - 10 = 0
        # delta_t = 60 - 20 - 15 = 25
        # 25 - 0 = 25 > 10 → cond_three срабатывает
        row = self._make_row(
            t_sticker=">50",
            t_observed=60.0,
            history_t_observed=[30],
            history_t_stickers=[">80"],
            history_t_environment=[20.0],
            history_t_excess=[10.0],
            t_environment=20.0,
            t_excess=15.0,
        )
        result = self.renderer.history_inspection_parser(row)
        assert "развитие дефекта" in result
        assert "Тпрев" in result

    # 8. history_t_observed = 0, t_observed = 0 → cond_one не срабатывает (0 falsy)
    def test_cond_one_falsy_values_skip(self):
        row = self._make_row(
            history_t_observed=[0],
            t_observed=0,
        )
        result = self.renderer.history_inspection_parser(row)
        # cond_one не срабатывает, проверяем что не "рост абсолютного"
        assert "рост абсолютного значения" not in result

    # 9. Несколько единиц в истории — выбирается по unit_name
    def test_selects_correct_index_from_history(self):
        # history_unit_names = ["РУ-0,4 кВ", "Щит-1"], unit_name = "Щит-1" → idx=1
        row = self._make_row(
            unit_name="Щит-1",
            history_unit_names=["РУ-0,4 кВ", "Щит-1"],
            history_t_observed=[10.0, 50.0],  # idx=1 → 50
            history_t_stickers=[">10", ">80"],  # idx=1 → 80
            t_sticker=">120",  # t_max = 120
            t_observed=55.0,  # t_max = 120
            history_t_environment=[5.0, 22.0],  # idx=1 → 22
            history_t_excess=[2.0, 12.0],  # idx=1 → 12
        )
        result = self.renderer.history_inspection_parser(row)
        assert "регистрация дефекта" in result
        assert "дефект" in result

    # 10. extract_item: строковое значение → t_sticker_parser
    def test_extract_item_parses_string(self):
        assert self.renderer.extract_item([">100"], 0) == 100

    # 11. extract_item: числовое значение → как есть
    def test_extract_item_returns_number_as_is(self):
        assert self.renderer.extract_item([45.0], 0) == 45.0

    # 12. extract_item: None → 0
    def test_extract_item_returns_zero_for_none(self):
        assert self.renderer.extract_item([None], 0) == 0

    # 13. extract_item: пустой список → 0
    def test_extract_item_returns_zero_for_empty_list(self):
        assert self.renderer.extract_item([], 0) == 0

    # 14. extract_item: idx вне диапазона → 0
    def test_extract_item_returns_zero_for_out_of_range(self):
        assert self.renderer.extract_item([1], 5) == 0

    # 15. to_nearest_ten: округление до ближайших 10
    def test_to_nearest_ten(self):
        assert self.renderer.to_nearest_ten(15) == 10
        assert self.renderer.to_nearest_ten(25) == 20
        assert self.renderer.to_nearest_ten(9) == 0
        assert self.renderer.to_nearest_ten(10) == 10

    # ─── inspector_major_parser ────────────────────────────────────────

    def _make_inspector_data(self, entries: list[dict]) -> list[dict]:
        """Создаёт список инспекторов для тестов."""
        return entries

    # 1. Базовый случай: один инспектор с должностью
    def test_single_inspector_with_position(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И.", "position_major": "Начальник отдела"},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert result == {"Иванов И.И.": "Начальник отдела"}

    # 2. Несколько разных инспекторов
    def test_multiple_different_inspectors(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И.", "position_major": "Начальник отдела"},
            {"full_name_major": "Петров П.П.", "position_major": "Ведущий инженер"},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert len(result) == 2
        assert result["Иванов И.И."] == "Начальник отдела"
        assert result["Петров П.П."] == "Ведущий инженер"

    # 3. Дубликаты: оставляется последнее вхождение
    def test_duplicates_keeps_last(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И.", "position_major": "Инженер"},
            {"full_name_major": "Иванов И.И.", "position_major": "Начальник отдела"},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert result == {"Иванов И.И.": "Начальник отдела"}

    # 4. position_major отсутствует → подставляется должность по умолчанию
    def test_missing_position_uses_default(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И."},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert result == {"Иванов И.И.": "Инженер теплового контроля"}

    # 5. position_major = None → подставляется должность по умолчанию
    def test_none_position_uses_default(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И.", "position_major": None},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert result == {"Иванов И.И.": "Инженер теплового контроля"}

    # 6. empty string position_major → подставляется должность по умолчанию
    def test_empty_string_position_uses_default(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И.", "position_major": ""},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert result == {"Иванов И.И.": "Инженер теплового контроля"}

    # 7. empty list → пустой результат
    def test_empty_list_returns_empty_dict(self):
        result = self.renderer.inspector_major_parser([])
        assert result == {}

    # 8. full_name_major отсутствует → элемент пропускается
    def test_missing_full_name_major_skipped(self):
        data = self._make_inspector_data([
            {"position_major": "Начальник"},
            {"full_name_major": "Петров П.П.", "position_major": "Инженер"},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert len(result) == 1
        assert "Петров П.П." in result

    # 9. full_name_major = None → элемент пропускается
    def test_none_full_name_major_skipped(self):
        data = self._make_inspector_data([
            {"full_name_major": None, "position_major": "Начальник"},
            {"full_name_major": "Петров П.П.", "position_major": "Инженер"},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert len(result) == 1
        assert "Петров П.П." in result

    # 10. Смешанные данные: дубликаты, пустые должности, разные имена
    def test_mixed_data(self):
        data = self._make_inspector_data([
            {"full_name_major": "Иванов И.И.", "position_major": "Инженер"},
            {"full_name_major": "Петров П.П."},
            {"full_name_major": "Иванов И.И.", "position_major": "Начальник отдела"},
            {"full_name_major": "Сидоров С.С.", "position_major": None},
        ])
        result = self.renderer.inspector_major_parser(data)
        assert len(result) == 3
        assert result["Иванов И.И."] == "Начальник отдела"
        assert result["Петров П.П."] == "Инженер теплового контроля"
        assert result["Сидоров С.С."] == "Инженер теплового контроля"

    # ─── inspector_minor_parser ────────────────────────────────────────

    def _make_minor_data(self, entries: list[dict]) -> list[dict]:
        """Создаёт список младших инспекторов для тестов."""
        return entries

    # 1. Один элемент с одним именем и должностью
    def test_single_name_single_position(self):
        data = self._make_minor_data([
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Начальник отдела"]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert result == {"Иванов И.И.": "Начальник отдела"}

    # 2. Один элемент с несколькими именами и должностями
    def test_multiple_names_in_one_item(self):
        data = self._make_minor_data([
            {
                "full_names_minor": ["Иванов И.И.", "Петров П.П."],
                "positions_minor": ["Инженер", "Ведущий инженер"],
            },
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 2
        assert result["Иванов И.И."] == "Инженер"
        assert result["Петров П.П."] == "Ведущий инженер"

    # 3. Несколько элементов с разными именами
    def test_multiple_items_different_names(self):
        data = self._make_minor_data([
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Инженер"]},
            {"full_names_minor": ["Петров П.П."], "positions_minor": ["Ведущий инженер"]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 2
        assert result["Иванов И.И."] == "Инженер"
        assert result["Петров П.П."] == "Ведущий инженер"

    # 4. Несколько элементов с пересечением имён (дубликаты, последнее вхождение)
    def test_duplicates_keeps_last_minor(self):
        data = self._make_minor_data([
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Инженер"]},
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Начальник отдела"]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert result == {"Иванов И.И.": "Начальник отдела"}

    # 5. Несколько имён в одном элементе + дубликаты между элементами
    def test_multiple_names_with_duplicates_across_items(self):
        data = self._make_minor_data([
            {
                "full_names_minor": ["Иванов И.И.", "Петров П.П."],
                "positions_minor": ["Инженер", "Ведущий инженер"],
            },
            {"full_names_minor": ["Сидоров С.С."], "positions_minor": ["Начальник отдела"]},
            {"full_names_minor": ["Петров П.П."], "positions_minor": ["Заместитель"]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 3
        assert result["Иванов И.И."] == "Инженер"
        assert result["Петров П.П."] == "Заместитель"  # последнее вхождение
        assert result["Сидоров С.С."] == "Начальник отдела"

    # 6. positions_minor = None → подставляется должность по умолчанию
    def test_none_position_uses_default_minor(self):
        data = self._make_minor_data([
            {"full_names_minor": ["Иванов И.И."], "positions_minor": [None]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert result == {"Иванов И.И.": "Инженер теплового контроля"}

    # 7. positions_minor = [""] (пустая строка) → подставляется должность по умолчанию
    def test_empty_string_position_uses_default_minor(self):
        data = self._make_minor_data([
            {"full_names_minor": ["Иванов И.И."], "positions_minor": [""]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert result == {"Иванов И.И.": "Инженер теплового контроля"}

    # 8. positions_minor короче full_names_minor → подставляется должность по умолчанию
    def test_positions_shorter_than_names_uses_default(self):
        data = self._make_minor_data([
            {
                "full_names_minor": ["Иванов И.И.", "Петров П.П.", "Сидоров С.С."],
                "positions_minor": ["Инженер"],
            },
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 3
        assert result["Иванов И.И."] == "Инженер"
        assert result["Петров П.П."] == "Инженер теплового контроля"
        assert result["Сидоров С.С."] == "Инженер теплового контроля"

    # 9. full_names_minor отсутствует → элемент пропускается
    def test_missing_full_names_minor_skipped(self):
        data = self._make_minor_data([
            {"positions_minor": ["Инженер"]},
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Начальник"]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 1
        assert "Иванов И.И." in result

    # 10. full_names_minor = None → элемент пропускается
    def test_none_full_names_minor_skipped(self):
        data = self._make_minor_data([
            {"full_names_minor": None, "positions_minor": ["Инженер"]},
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Начальник"]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 1
        assert "Иванов И.И." in result

    # 11. positions_minor отсутствует → подставляется должность по умолчанию
    def test_missing_positions_minor_uses_default(self):
        data = self._make_minor_data([
            {"full_names_minor": ["Иванов И.И."]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert result == {"Иванов И.И.": "Инженер теплового контроля"}

    # 12. empty list → пустой результат
    def test_empty_list_returns_empty_dict_minor(self):
        result = self.renderer.inspector_minor_parser([])
        assert result == {}

    # 13. Смешанные данные: все случаи вместе
    def test_mixed_data_minor(self):
        data = self._make_minor_data([
            {
                "full_names_minor": ["Иванов И.И.", "Петров П.П."],
                "positions_minor": ["Инженер", None],
            },
            {"full_names_minor": ["Иванов И.И."], "positions_minor": ["Начальник отдела"]},
            {"full_names_minor": ["Сидоров С.С."], "positions_minor": [""]},
            {"full_names_minor": ["Козлов К.К."]},
        ])
        result = self.renderer.inspector_minor_parser(data)
        assert len(result) == 4
        assert result["Иванов И.И."] == "Начальник отдела"  # последнее вхождение
        assert result["Петров П.П."] == "Инженер теплового контроля"  # None → дефолт
        assert result["Сидоров С.С."] == "Инженер теплового контроля"  # "" → дефолт
        assert result["Козлов К.К."] == "Инженер теплового контроля"  # нет positions_minor → дефолт
