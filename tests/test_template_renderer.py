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
