# test_template_renderer.py
from jinja2 import Environment
import pytest
from pathlib import Path
from unittest.mock import Mock
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
