"""Unit tests for report repository."""

from pathlib import Path

import pytest

from render.models import ParameterType
from render.services.repository import Report, ReportRepository


class TestReportRepository:
    """Tests for ReportRepository."""

    def test_load_valid_report(self, temp_reports_dir: Path):
        """Test loading a valid report from filesystem."""
        # Create a valid report structure
        report_dir = temp_reports_dir / "test-report"
        report_dir.mkdir()

        # Create metadata.yaml
        (report_dir / "metadata.yaml").write_text("""
name: "Test Report"
description: "A test report"
version: "1.0"
format: "weasyprint"
timeout: 120
parameters:
  - name: user_id
    type: integer
    required: true
    description: "User ID"
""")

        # Create template
        (report_dir / "index.html.j2").write_text("<html><body>Test</body></html>")

        # Create SQL query
        (report_dir / "query.sql").write_text(
            "SELECT * FROM users WHERE id = :user_id;"
        )

        # Load repository
        repo = ReportRepository(str(temp_reports_dir))

        # Verify report was loaded
        reports = repo.list_reports()
        assert len(reports) == 1
        assert reports[0].id == "test-report"
        assert reports[0].name == "Test Report"

    def test_get_report_metadata(self, temp_reports_dir: Path):
        """Test retrieving report metadata."""
        # Create report
        report_dir = temp_reports_dir / "sales-report"
        report_dir.mkdir()

        (report_dir / "metadata.yaml").write_text("""
name: "Sales Report"
description: "Monthly sales"
version: "2.0"
format: "weasyprint"
parameters:
  - name: month
    type: string
    required: true
  - name: year
    type: integer
    required: true
""")
        (report_dir / "index.html.j2").write_text("<html></html>")
        (report_dir / "sales.sql").write_text("SELECT * FROM sales;")

        repo = ReportRepository(str(temp_reports_dir))
        metadata = repo.get_metadata("sales-report")

        assert metadata.id == "sales-report"
        assert metadata.name == "Sales Report"
        assert metadata.description == "Monthly sales"
        assert metadata.version == "2.0"
        assert len(metadata.parameters) == 2
        assert metadata.parameters[0].name == "month"
        assert metadata.parameters[0].type == ParameterType.STRING
        assert metadata.parameters[1].name == "year"
        assert metadata.parameters[1].type == ParameterType.INTEGER

    def test_get_nonexistent_report(self, temp_reports_dir: Path):
        """Test getting a report that doesn't exist."""
        repo = ReportRepository(str(temp_reports_dir))

        with pytest.raises(ValueError, match="Report not found"):
            repo.get_report("nonexistent-report")

    def test_missing_metadata_file(self, temp_reports_dir: Path):
        """Test report without metadata.yaml is skipped."""
        report_dir = temp_reports_dir / "invalid-report"
        report_dir.mkdir()
        (report_dir / "index.html.j2").write_text("<html></html>")
        (report_dir / "query.sql").write_text("SELECT 1;")

        repo = ReportRepository(str(temp_reports_dir))

        # Report should not be loaded
        assert len(repo.list_reports()) == 0

    def test_missing_template_file(self, temp_reports_dir: Path):
        """Test report without template is skipped."""
        report_dir = temp_reports_dir / "invalid-report"
        report_dir.mkdir()
        (report_dir / "metadata.yaml").write_text("name: Test\nformat: weasyprint\n")
        (report_dir / "query.sql").write_text("SELECT 1;")

        repo = ReportRepository(str(temp_reports_dir))

        # Report should not be loaded
        assert len(repo.list_reports()) == 0

    def test_missing_sql_files(self, temp_reports_dir: Path):
        """Test report without SQL files is skipped."""
        report_dir = temp_reports_dir / "invalid-report"
        report_dir.mkdir()
        (report_dir / "metadata.yaml").write_text("name: Test\nformat: weasyprint\n")
        (report_dir / "index.html.j2").write_text("<html></html>")

        repo = ReportRepository(str(temp_reports_dir))

        # Report should not be loaded
        assert len(repo.list_reports()) == 0

    def test_multiple_reports(self, temp_reports_dir: Path):
        """Test loading multiple reports."""
        # Create first report
        report1 = temp_reports_dir / "report1"
        report1.mkdir()
        (report1 / "metadata.yaml").write_text("name: Report 1\nformat: weasyprint\n")
        (report1 / "index.html.j2").write_text("<html></html>")
        (report1 / "query.sql").write_text("SELECT 1;")

        # Create second report
        report2 = temp_reports_dir / "report2"
        report2.mkdir()
        (report2 / "metadata.yaml").write_text("name: Report 2\nformat: weasyprint\n")
        (report2 / "index.html.j2").write_text("<html></html>")
        (report2 / "query.sql").write_text("SELECT 2;")

        repo = ReportRepository(str(temp_reports_dir))
        reports = repo.list_reports()

        assert len(reports) == 2
        report_ids = {r.id for r in reports}
        assert report_ids == {"report1", "report2"}

    def test_reload_reports(self, temp_reports_dir: Path):
        """Test reloading reports from filesystem."""
        # Create initial report
        report_dir = temp_reports_dir / "test-report"
        report_dir.mkdir()
        (report_dir / "metadata.yaml").write_text("name: Test\nformat: weasyprint\n")
        (report_dir / "index.html.j2").write_text("<html></html>")
        (report_dir / "query.sql").write_text("SELECT 1;")

        repo = ReportRepository(str(temp_reports_dir))
        assert len(repo.list_reports()) == 1

        # Add another report
        report2_dir = temp_reports_dir / "new-report"
        report2_dir.mkdir()
        (report2_dir / "metadata.yaml").write_text("name: New\nformat: weasyprint\n")
        (report2_dir / "index.html.j2").write_text("<html></html>")
        (report2_dir / "query.sql").write_text("SELECT 2;")

        # Reload
        repo.reload()
        assert len(repo.list_reports()) == 2


class TestReport:
    """Tests for Report class."""

    def test_report_properties(self, mock_report: Report):
        """Test Report object properties."""
        assert mock_report.id == "test-report"
        assert mock_report.metadata.name == "Test Report"
        assert mock_report.template_path.name == "index.html.j2"
        assert len(mock_report.query_files) > 0

    def test_query_files_sorted(self, temp_reports_dir: Path, sample_report_metadata):
        """Test query files are sorted alphabetically."""
        report_dir = temp_reports_dir / "test"
        report_dir.mkdir()

        # Create queries in non-alphabetical order
        (report_dir / "z_query.sql").write_text("SELECT 1;")
        (report_dir / "a_query.sql").write_text("SELECT 2;")
        (report_dir / "m_query.sql").write_text("SELECT 3;")

        report = Report(report_dir, sample_report_metadata)

        query_names = [f.stem for f in report.query_files]
        assert query_names == ["a_query", "m_query", "z_query"]
