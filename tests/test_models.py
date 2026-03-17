"""Unit tests for data models."""

import pytest
from pydantic import ValidationError

from render.models import (
    ParameterType,
    RenderResult,
    RenderStatus,
    ReportListItem,
    ReportMetadata,
    ReportParameter,
)


class TestReportListItem:
    """Tests for ReportListItem model."""

    def test_create_valid_item(self):
        """Test creating a valid report list item."""
        item = ReportListItem(id="test-report", name="Test Report")
        assert item.id == "test-report"
        assert item.name == "Test Report"

    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        with pytest.raises(ValidationError):
            ReportListItem(id="test-report")  # missing name

        with pytest.raises(ValidationError):
            ReportListItem(name="Test Report")  # missing id


class TestReportParameter:
    """Tests for ReportParameter model."""

    def test_create_required_parameter(self):
        """Test creating a required parameter."""
        param = ReportParameter(
            name="user_id",
            type=ParameterType.INTEGER,
            required=True,
            description="User identifier",
        )
        assert param.name == "user_id"
        assert param.type == ParameterType.INTEGER
        assert param.required is True
        assert param.default is None

    def test_create_optional_parameter_with_default(self):
        """Test creating an optional parameter with default value."""
        param = ReportParameter(
            name="schema_name",
            type=ParameterType.STRING,
            required=False,
            default="public",
        )
        assert param.required is False
        assert param.default == "public"

    def test_parameter_with_enum(self):
        """Test parameter with enumerated values."""
        param = ReportParameter(
            name="status",
            type=ParameterType.STRING,
            enum=["active", "inactive", "pending"],
        )
        assert param.enum == ["active", "inactive", "pending"]

    def test_all_parameter_types(self):
        """Test all supported parameter types."""
        types = [
            ParameterType.STRING,
            ParameterType.INTEGER,
            ParameterType.FLOAT,
            ParameterType.BOOLEAN,
            ParameterType.DATE,
            ParameterType.DATETIME,
        ]
        for param_type in types:
            param = ReportParameter(name="test", type=param_type)
            assert param.type == param_type


class TestReportMetadata:
    """Tests for ReportMetadata model."""

    def test_create_minimal_metadata(self):
        """Test creating metadata with minimal required fields."""
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
        )
        assert metadata.id == "test-report"
        assert metadata.name == "Test Report"
        assert metadata.version == "1.0"  # default
        assert metadata.parameters == []  # default

    def test_create_full_metadata(self):
        """Test creating metadata with all fields."""
        metadata = ReportMetadata(
            id="sales-report",
            name="Sales Report",
            description="Monthly sales analysis",
            version="2.0",
            timeout=300,
            parameters=[
                ReportParameter(
                    name="month",
                    type=ParameterType.STRING,
                    required=True,
                )
            ],
        )
        assert metadata.description == "Monthly sales analysis"
        assert metadata.version == "2.0"
        assert metadata.timeout == 300
        assert len(metadata.parameters) == 1

    def test_metadata_with_multiple_parameters(self):
        """Test metadata with multiple parameters."""
        metadata = ReportMetadata(
            id="test",
            name="Test",
            parameters=[
                ReportParameter(
                    name="start_date", type=ParameterType.DATE, required=True
                ),
                ReportParameter(
                    name="end_date", type=ParameterType.DATE, required=True
                ),
                ReportParameter(name="limit", type=ParameterType.INTEGER, default=100),
            ],
        )
        assert len(metadata.parameters) == 3
        assert metadata.parameters[0].name == "start_date"
        assert metadata.parameters[2].default == 100


class TestRenderStatus:
    """Tests for RenderStatus enum."""

    def test_all_statuses(self):
        """Test all render status values."""
        assert RenderStatus.PENDING.value == "pending"
        assert RenderStatus.RUNNING.value == "running"
        assert RenderStatus.COMPLETED.value == "completed"
        assert RenderStatus.FAILED.value == "failed"

    def test_status_comparison(self):
        """Test status enum comparison."""
        assert RenderStatus.PENDING == RenderStatus.PENDING
        assert RenderStatus.PENDING != RenderStatus.RUNNING


class TestRenderResult:
    """Tests for RenderResult model."""

    def test_pending_result(self):
        """Test creating a pending result."""
        result = RenderResult(status=RenderStatus.PENDING)
        assert result.status == RenderStatus.PENDING
        assert result.pdf_bytes is None
        assert result.error_message is None

    def test_running_result(self):
        """Test creating a running result."""
        result = RenderResult(status=RenderStatus.RUNNING)
        assert result.status == RenderStatus.RUNNING
        assert result.pdf_bytes is None
        assert result.error_message is None

    def test_completed_result(self):
        """Test creating a completed result with PDF."""
        pdf_data = b"%PDF-1.4 test content"
        result = RenderResult(
            status=RenderStatus.COMPLETED,
            pdf_bytes=pdf_data,
        )
        assert result.status == RenderStatus.COMPLETED
        assert result.pdf_bytes == pdf_data
        assert result.error_message is None

    def test_failed_result(self):
        """Test creating a failed result with error."""
        result = RenderResult(
            status=RenderStatus.FAILED,
            error_message="Database connection failed",
        )
        assert result.status == RenderStatus.FAILED
        assert result.pdf_bytes is None
        assert result.error_message == "Database connection failed"

    def test_result_serialization(self):
        """Test result can be serialized to dict."""
        result = RenderResult(
            status=RenderStatus.COMPLETED,
            pdf_bytes=b"test",
        )
        data = result.model_dump()
        assert data["status"] == RenderStatus.COMPLETED
        assert data["pdf_bytes"] == b"test"
