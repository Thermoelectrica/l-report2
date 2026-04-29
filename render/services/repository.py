"""Report repository scanner and loader."""

import logging
from pathlib import Path
from typing import Dict, List

import yaml

from ..config import settings
from ..models import ParameterType, ReportListItem, ReportMetadata, ReportParameter

logger = logging.getLogger(__name__)


class Report:
    """Represents a loaded report with its metadata and files."""

    def __init__(self, path: Path, metadata: ReportMetadata):
        self.path = path
        self.metadata = metadata
        self.template_path = path / "index.html.j2"
        self.query_files = sorted(path.glob("*.sql"))

    @property
    def id(self) -> str:
        """Report ID is the folder name."""
        return self.path.name


class ReportRepository:
    """Scans and manages report templates from filesystem."""

    def __init__(self, reports_path: str):
        self.reports_path = Path(reports_path)
        self._reports: Dict[str, Report] = {}
        self._load_reports()

    def _load_reports(self):
        """Scan directory and load all valid reports."""
        if not self.reports_path.exists():
            logger.warning(f"Reports path does not exist: {self.reports_path}")
            return

        if not self.reports_path.is_dir():
            logger.error(f"Reports path is not a directory: {self.reports_path}")
            return

        for report_dir in self.reports_path.iterdir():
            if not report_dir.is_dir():
                continue
            
            # Skip dotfiles/dotfolders (e.g., .git)
            if report_dir.name.startswith('.'):
                continue

            try:
                report = self._load_report(report_dir)
                self._reports[report.id] = report
                logger.info(f"Loaded report: {report.id}")
            except Exception as e:
                logger.error(f"Failed to load report {report_dir.name}: {e}")

    def _load_report(self, report_dir: Path) -> Report:
        """Load and validate a single report."""
        # Check for required files
        metadata_file = report_dir / "metadata.yaml"
        template_file = report_dir / "index.html.j2"

        if not metadata_file.exists():
            raise ValueError(f"Missing metadata.yaml in {report_dir.name}")
        if not template_file.exists():
            raise ValueError(f"Missing index.html.j2 in {report_dir.name}")

        # Check for at least one SQL file
        sql_files = list(report_dir.glob("*.sql"))
        if not sql_files:
            raise ValueError(f"No SQL files found in {report_dir.name}")

        # Load metadata
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata_dict = yaml.safe_load(f)

        if not metadata_dict:
            raise ValueError(f"Empty metadata.yaml in {report_dir.name}")

        # Parse parameters
        parameters = []
        for param in metadata_dict.get("parameters", []):
            parameters.append(
                ReportParameter(
                    name=param["name"],
                    type=ParameterType(param["type"]),
                    required=param.get("required", False),
                    description=param.get("description"),
                    enum=param.get("enum"),
                    enum_query=param.get("enum_query"),
                    default=param.get("default"),
                )
            )

        metadata = ReportMetadata(
            id=report_dir.name,
            name=metadata_dict.get("name", report_dir.name),
            description=metadata_dict.get("description"),
            version=metadata_dict.get("version", "1.0"),
            format=metadata_dict["format"],  # Required field
            timeout=metadata_dict.get("timeout"),
            cache_ttl_minutes=metadata_dict.get("cache_ttl_minutes"),
            parameters=parameters,
        )

        return Report(report_dir, metadata)

    def list_reports(self) -> List[ReportListItem]:
        """Get list of all available reports."""
        return [
            ReportListItem(id=report.id, name=report.metadata.name)
            for report in self._reports.values()
        ]

    def get_report(self, report_id: str) -> Report:
        """Get specific report by ID, reloading from disk each time."""
        report_dir = self.reports_path / report_id
        
        if not report_dir.exists() or not report_dir.is_dir():
            raise ValueError(f"Report not found: {report_id}")
        
        try:
            # Reload the report from disk to pick up any changes
            report = self._load_report(report_dir)
            logger.info(f"Reloaded report from disk: {report_id}")
            return report
        except Exception as e:
            logger.error(f"Failed to reload report {report_id}: {e}")
            raise ValueError(f"Failed to load report {report_id}: {e}")

    def get_metadata(self, report_id: str) -> ReportMetadata:
        """Get report metadata, reloading from disk each time."""
        return self.get_report(report_id).metadata

    def reload(self):
        """Reload all reports from filesystem."""
        self._reports.clear()
        self._load_reports()
        logger.info(f"Reloaded {len(self._reports)} reports")


# Global repository instance
repository = ReportRepository(settings.reports_path)
