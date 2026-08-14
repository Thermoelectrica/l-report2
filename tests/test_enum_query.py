"""Tests for dynamic enum query functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from render.models import ParameterType, ReportMetadata, ReportParameter
from render.services.render_service import RenderServiceImpl
from render.services.repository import Report


class TestEnumQuery:
    """Tests for dynamic enum query functionality."""

    @pytest.mark.asyncio
    async def test_execute_enum_query(self, temp_reports_dir):
        """Test that enum queries can be executed and return values."""
        from render.services.query_executor import QueryExecutor

        # Create a test enum query file
        report_dir = temp_reports_dir / "test-report"
        report_dir.mkdir()
        enum_query_file = report_dir / "enum_values.sql"
        enum_query_file.write_text(
            "SELECT unnest(ARRAY['val1', 'val2', 'val3']) AS value;"
        )

        # Mock the query executor
        executor = QueryExecutor()

        # Mock the connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        # Create mock rows with keys() method
        class MockRow:
            def __init__(self, data):
                self._data = data

            def keys(self):
                return list(self._data.keys())

            def __getitem__(self, key):
                return self._data[key]

        mock_rows = [
            MockRow({"value": "val1"}),
            MockRow({"value": "val2"}),
            MockRow({"value": "val3"}),
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        # Mock the pool with proper async context manager
        mock_acquire = AsyncMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)

        executor.pool = mock_pool

        # Execute the enum query
        enum_values = await executor.execute_enum_query(enum_query_file)

        # Verify we got values back
        assert enum_values is not None
        assert isinstance(enum_values, list)
        assert len(enum_values) == 3
        assert enum_values == ["val1", "val2", "val3"]

    @pytest.mark.asyncio
    async def test_metadata_with_enum_query(self, temp_reports_dir):
        """Test that metadata resolves enum_query to enum values."""
        # Create a test report with enum_query
        report_dir = temp_reports_dir / "test-report"
        report_dir.mkdir()

        # Create enum query file
        enum_query_file = report_dir / "enum_values.sql"
        enum_query_file.write_text("SELECT unnest(ARRAY['opt1', 'opt2']) AS value;")

        # Create metadata with enum_query parameter
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="dynamic_param",
                    type=ParameterType.STRING,
                    enum_query="enum_values.sql",
                )
            ],
        )

        report = Report(report_dir, metadata)

        # Mock repository and query executor
        service = RenderServiceImpl()

        with patch("render.services.render_service.repository") as mock_repo, patch(
            "render.services.render_service.query_executor"
        ) as mock_executor:

            mock_repo.get_metadata.return_value = metadata
            mock_repo.get_report.return_value = report
            mock_executor.pool = MagicMock()  # Pretend it's initialized
            mock_executor.execute_enum_query = AsyncMock(return_value=["opt1", "opt2"])

            # Get metadata
            result_metadata = await service.getReportMetadata("test-report")

            # Verify enum values were resolved
            assert len(result_metadata.parameters) == 1
            param = result_metadata.parameters[0]
            assert param.enum == ["opt1", "opt2"]
            mock_executor.execute_enum_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_static_enum_still_works(self):
        """Test that static enum values still work alongside enum_query."""
        # Create metadata with static enum
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="static_param",
                    type=ParameterType.STRING,
                    enum=["abc", "def", "ghi"],
                )
            ],
        )

        service = RenderServiceImpl()

        with patch("render.services.render_service.repository") as mock_repo, patch(
            "render.services.render_service.query_executor"
        ) as mock_executor:

            mock_repo.get_metadata.return_value = metadata
            mock_repo.get_report.return_value = MagicMock()
            mock_executor.pool = MagicMock()  # Pretend it's initialized

            # Get metadata
            result_metadata = await service.getReportMetadata("test-report")

            # Verify static enum values are preserved
            assert len(result_metadata.parameters) == 1
            param = result_metadata.parameters[0]
            assert param.enum == ["abc", "def", "ghi"]
            # Should not call execute_enum_query for static enums
            mock_executor.execute_enum_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_enum_query_file_not_found(self, temp_reports_dir):
        """Test handling when enum_query file doesn't exist."""
        # Create a test report
        report_dir = temp_reports_dir / "test-report"
        report_dir.mkdir()

        # Create metadata with enum_query that doesn't exist
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="dynamic_param",
                    type=ParameterType.STRING,
                    enum_query="nonexistent.sql",
                )
            ],
        )

        report = Report(report_dir, metadata)

        service = RenderServiceImpl()

        with patch("render.services.render_service.repository") as mock_repo, patch(
            "render.services.render_service.query_executor"
        ) as mock_executor:

            mock_repo.get_metadata.return_value = metadata
            mock_repo.get_report.return_value = report
            mock_executor.pool = MagicMock()  # Pretend it's initialized

            # Get metadata - should not crash
            result_metadata = await service.getReportMetadata("test-report")

            # Verify parameter exists but enum is None (not resolved)
            assert len(result_metadata.parameters) == 1
            param = result_metadata.parameters[0]
            assert param.enum is None
            # Should not call execute_enum_query since file doesn't exist
            mock_executor.execute_enum_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_executor_not_initialized(self):
        """Test handling when query executor is not initialized."""
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="dynamic_param",
                    type=ParameterType.STRING,
                    enum_query="enum_values.sql",
                )
            ],
        )

        service = RenderServiceImpl()

        with patch("render.services.render_service.repository") as mock_repo, patch(
            "render.services.render_service.query_executor"
        ) as mock_executor:

            mock_repo.get_metadata.return_value = metadata
            mock_repo.get_report.return_value = MagicMock()
            mock_executor.pool = None  # Not initialized

            # Get metadata - should not crash
            result_metadata = await service.getReportMetadata("test-report")

            # Verify parameter exists but enum is None (not resolved)
            assert len(result_metadata.parameters) == 1
            param = result_metadata.parameters[0]
            assert param.enum is None
            # Should not call execute_enum_query since pool is None
            mock_executor.execute_enum_query.assert_not_called()

    def test_report_parameter_accepts_enum_query(self):
        """Test that ReportParameter model accepts enum_query field."""
        param = ReportParameter(
            name="test_param", type=ParameterType.STRING, enum_query="test.sql"
        )

        assert param.enum_query == "test.sql"
        assert param.enum is None  # Should be None until resolved
