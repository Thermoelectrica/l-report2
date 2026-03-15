"""Integration tests for the complete rendering workflow."""

import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime

from render.services.repository import ReportRepository
from render.services.template_renderer import TemplateRenderer
from render.models import RenderStatus


class TestReportWorkflow:
    """Integration tests for complete report workflow."""

    def test_load_and_render_template(self, temp_reports_dir: Path, sample_parameters, sample_query_results):
        """Test loading a report and rendering its template."""
        # Create a complete report
        report_dir = temp_reports_dir / "integration-test"
        report_dir.mkdir()
        
        # Create metadata
        (report_dir / "metadata.yaml").write_text("""
name: "Integration Test Report"
description: "Test report for integration testing"
version: "1.0"
parameters:
  - name: start_date
    type: date
    required: true
  - name: end_date
    type: date
    required: true
  - name: schema_name
    type: string
    required: false
    default: "public"
""")
        
        # Create template
        (report_dir / "index.html.j2").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ globals.report_name }}</title>
</head>
<body>
    <h1>{{ globals.report_name }}</h1>
    <p>Generated: {{ globals.generated_at }}</p>
    <p>Period: {{ params.start_date }} to {{ params.end_date }}</p>
    <p>Schema: {{ params.schema_name }}</p>
    
    <h2>Tables</h2>
    <table>
        <tr>
            <th>Schema</th>
            <th>Table</th>
            <th>Size</th>
        </tr>
        {% for row in queries.tables_list %}
        <tr>
            <td>{{ row.schema_name }}</td>
            <td>{{ row.table_name }}</td>
            <td>{{ row.total_size }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
""")
        
        # Create SQL query
        (report_dir / "tables_list.sql").write_text("""
SELECT 
    schemaname as schema_name,
    tablename as table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size
FROM pg_tables
WHERE schemaname = :schema_name
ORDER BY tablename;
""")
        
        # Load repository
        repo = ReportRepository(str(temp_reports_dir))
        report = repo.get_report("integration-test")
        
        # Verify report loaded correctly
        assert report.id == "integration-test"
        assert report.metadata.name == "Integration Test Report"
        assert len(report.metadata.parameters) == 3
        assert len(report.query_files) == 1
        
        # Render template
        renderer = TemplateRenderer()
        html = renderer.render(report, sample_parameters, sample_query_results)
        
        # Verify rendered HTML
        assert "Integration Test Report" in html
        assert sample_parameters["start_date"] in html
        assert sample_parameters["end_date"] in html
        assert sample_parameters["schema_name"] in html
        assert "public" in html  # From query results
        assert "users" in html  # From query results

    def test_template_with_custom_filters(self, temp_reports_dir: Path):
        """Test template rendering with custom Jinja2 filters."""
        # Create report with filters
        report_dir = temp_reports_dir / "filter-test"
        report_dir.mkdir()
        
        (report_dir / "metadata.yaml").write_text("name: Filter Test\n")
        (report_dir / "index.html.j2").write_text("""
<html>
<body>
    <p>Number: {{ 1234.56 | format_number }}</p>
    <p>Date: {{ params.date_value | format_date }}</p>
</body>
</html>
""")
        (report_dir / "query.sql").write_text("SELECT 1;")
        
        repo = ReportRepository(str(temp_reports_dir))
        report = repo.get_report("filter-test")
        
        renderer = TemplateRenderer()
        html = renderer.render(
            report,
            {"date_value": datetime(2024, 1, 15)},
            {"query": pd.DataFrame()}
        )
        
        # Verify filters worked
        assert "1,234.56" in html
        assert "2024-01-15" in html

    def test_multiple_queries_in_template(self, temp_reports_dir: Path, sample_query_results):
        """Test template with multiple query results."""
        report_dir = temp_reports_dir / "multi-query"
        report_dir.mkdir()
        
        (report_dir / "metadata.yaml").write_text("name: Multi Query\n")
        (report_dir / "index.html.j2").write_text("""
<html>
<body>
    <h2>Tables</h2>
    {% for row in queries.tables_list %}
    <p>{{ row.table_name }}</p>
    {% endfor %}
    
    <h2>Stats</h2>
    {% for row in queries.table_stats %}
    <p>{{ row.table_name }}: {{ row.row_count }}</p>
    {% endfor %}
</body>
</html>
""")
        (report_dir / "tables_list.sql").write_text("SELECT 1;")
        (report_dir / "table_stats.sql").write_text("SELECT 2;")
        
        repo = ReportRepository(str(temp_reports_dir))
        report = repo.get_report("multi-query")
        
        renderer = TemplateRenderer()
        html = renderer.render(report, {}, sample_query_results)
        
        # Verify both queries rendered
        assert "users" in html
        assert "orders" in html
        assert "100" in html  # row count
        assert "500" in html  # row count


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_report_discovery_and_metadata_retrieval(self, temp_reports_dir: Path):
        """Test discovering reports and retrieving their metadata."""
        # Create multiple reports
        for i in range(3):
            report_dir = temp_reports_dir / f"report{i}"
            report_dir.mkdir()
            (report_dir / "metadata.yaml").write_text(f"""
name: "Report {i}"
description: "Test report {i}"
parameters:
  - name: param{i}
    type: string
    required: true
""")
            (report_dir / "index.html.j2").write_text("<html></html>")
            (report_dir / "query.sql").write_text("SELECT 1;")
        
        # Load repository
        repo = ReportRepository(str(temp_reports_dir))
        
        # List all reports
        reports = repo.list_reports()
        assert len(reports) == 3
        
        # Get metadata for each
        for i in range(3):
            metadata = repo.get_metadata(f"report{i}")
            assert metadata.name == f"Report {i}"
            assert metadata.description == f"Test report {i}"
            assert len(metadata.parameters) == 1
            assert metadata.parameters[0].name == f"param{i}"

    def test_parameter_validation_workflow(self, temp_reports_dir: Path):
        """Test parameter validation in metadata."""
        report_dir = temp_reports_dir / "param-test"
        report_dir.mkdir()
        
        (report_dir / "metadata.yaml").write_text("""
name: "Parameter Test"
parameters:
  - name: required_param
    type: string
    required: true
    description: "This is required"
  - name: optional_param
    type: integer
    required: false
    default: 100
  - name: enum_param
    type: string
    required: false
    enum: ["option1", "option2", "option3"]
""")
        (report_dir / "index.html.j2").write_text("<html></html>")
        (report_dir / "query.sql").write_text("SELECT 1;")
        
        repo = ReportRepository(str(temp_reports_dir))
        metadata = repo.get_metadata("param-test")
        
        # Verify parameter definitions
        params = {p.name: p for p in metadata.parameters}
        
        assert params["required_param"].required is True
        assert params["optional_param"].required is False
        assert params["optional_param"].default == 100
        assert params["enum_param"].enum == ["option1", "option2", "option3"]
