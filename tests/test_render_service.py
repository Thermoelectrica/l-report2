"""Unit tests for render service."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from render.services.render_service import RenderServiceImpl
from render.models import RenderStatus, RenderResult
from render.database.models import Render


class TestRenderServiceImpl:
    """Tests for RenderServiceImpl."""

    def test_calculate_hash(self):
        """Test parameter hash calculation."""
        service = RenderServiceImpl()
        
        # Same inputs should produce same hash
        hash1 = service._calculate_hash("report1", {"a": 1, "b": 2})
        hash2 = service._calculate_hash("report1", {"a": 1, "b": 2})
        assert hash1 == hash2
        
        # Different parameter order should produce same hash (sorted)
        hash3 = service._calculate_hash("report1", {"b": 2, "a": 1})
        assert hash1 == hash3
        
        # Different values should produce different hash
        hash4 = service._calculate_hash("report1", {"a": 1, "b": 3})
        assert hash1 != hash4
        
        # Different report ID should produce different hash
        hash5 = service._calculate_hash("report2", {"a": 1, "b": 2})
        assert hash1 != hash5

    def test_calculate_hash_deterministic(self):
        """Test hash is deterministic across runs."""
        service = RenderServiceImpl()
        
        params = {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "schema": "public",
        }
        
        # Calculate hash multiple times
        hashes = [
            service._calculate_hash("test-report", params)
            for _ in range(10)
        ]
        
        # All should be identical
        assert len(set(hashes)) == 1

    def test_list_reports(self):
        """Test listing reports."""
        service = RenderServiceImpl()
        
        with patch('render.services.render_service.repository') as mock_repo:
            mock_repo.list_reports.return_value = [
                MagicMock(id="report1", name="Report 1"),
                MagicMock(id="report2", name="Report 2"),
            ]
            
            reports = service.listReports()
            
            assert len(reports) == 2
            mock_repo.list_reports.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_report_metadata(self):
        """Test getting report metadata."""
        service = RenderServiceImpl()
        
        with patch('render.services.render_service.repository') as mock_repo:
            with patch('render.services.render_service.query_executor') as mock_qe:
                mock_qe.pool = None  # Simulate uninitialized query executor
                mock_metadata = MagicMock()
                mock_metadata.id = "test-report"
                mock_metadata.name = "Test Report"
                mock_metadata.parameters = []
                mock_repo.get_metadata.return_value = mock_metadata
                mock_repo.get_report.return_value = MagicMock()
                
                metadata = await service.getReportMetadata("test-report")
                
                assert metadata.id == "test-report"
                assert metadata.name == "Test Report"
                mock_repo.get_metadata.assert_called_once_with("test-report")

    @pytest.mark.asyncio
    async def test_get_render_status_pending(self, db_session):
        """Test getting status when no render exists."""
        service = RenderServiceImpl()
        
        with patch('render.services.render_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = db_session
            
            result = await service.getRenderStatus("test-report", {"param": "value"})
            
            assert result.status == RenderStatus.PENDING
            assert result.pdf_bytes is None
            assert result.error_message is None

    @pytest.mark.asyncio
    async def test_get_render_status_running(self, db_session):
        """Test getting status for running render."""
        service = RenderServiceImpl()
        params = {"test": "value"}
        cache_key = service._calculate_hash("test-report", params)
        
        # Create running render
        render = Render(
            parameter_hash=cache_key,
            report_id="test-report",
            parameters_json='{"test": "value"}',
            status=RenderStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )
        db_session.add(render)
        await db_session.commit()
        
        with patch('render.services.render_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = db_session
            
            result = await service.getRenderStatus("test-report", params)
            
            assert result.status == RenderStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_render_status_failed(self, db_session):
        """Test getting status for failed render."""
        service = RenderServiceImpl()
        params = {"test": "value"}
        cache_key = service._calculate_hash("test-report", params)
        error_msg = "Database connection failed"
        
        # Create failed render
        render = Render(
            parameter_hash=cache_key,
            report_id="test-report",
            parameters_json='{"test": "value"}',
            status=RenderStatus.FAILED.value,
            error_message=error_msg,
            completed_at=datetime.utcnow(),
        )
        db_session.add(render)
        await db_session.commit()
        
        with patch('render.services.render_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = db_session
            
            result = await service.getRenderStatus("test-report", params)
            
            assert result.status == RenderStatus.FAILED
            assert result.error_message == error_msg

    @pytest.mark.asyncio
    async def test_get_render_status_completed_valid_cache(self, db_session, sample_pdf_bytes):
        """Test getting status for completed render with valid cache."""
        service = RenderServiceImpl(cache_ttl_hours=24)
        params = {"test": "value"}
        cache_key = service._calculate_hash("test-report", params)
        
        # Create completed render (recent)
        render = Render(
            parameter_hash=cache_key,
            report_id="test-report",
            parameters_json='{"test": "value"}',
            status=RenderStatus.COMPLETED.value,
            completed_at=datetime.utcnow(),  # Just completed
            pdf_path="/path/to/pdf",
        )
        db_session.add(render)
        await db_session.commit()
        
        # Mock storage
        mock_storage = AsyncMock()
        mock_storage.retrieve = AsyncMock(return_value=sample_pdf_bytes)
        
        with patch('render.services.render_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = db_session
            service.storage = mock_storage
            
            result = await service.getRenderStatus("test-report", params)
            
            assert result.status == RenderStatus.COMPLETED
            assert result.pdf_bytes == sample_pdf_bytes
            mock_storage.retrieve.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_get_render_status_completed_expired_cache(self, db_session):
        """Test getting status for completed render with expired cache."""
        service = RenderServiceImpl(cache_ttl_hours=24)
        params = {"test": "value"}
        cache_key = service._calculate_hash("test-report", params)
        
        # Create completed render (old)
        old_time = datetime.utcnow() - timedelta(hours=25)
        render = Render(
            parameter_hash=cache_key,
            report_id="test-report",
            parameters_json='{"test": "value"}',
            status=RenderStatus.COMPLETED.value,
            completed_at=old_time,
            pdf_path="/path/to/pdf",
        )
        db_session.add(render)
        await db_session.commit()
        
        with patch('render.services.render_service.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value = db_session
            
            result = await service.getRenderStatus("test-report", params)
            
            # Should return PENDING for expired cache
            assert result.status == RenderStatus.PENDING


class TestRenderServiceIntegration:
    """Integration tests for render service workflow."""

    @pytest.mark.asyncio
    async def test_execute_render_workflow(self):
        """Test the complete render execution workflow."""
        service = RenderServiceImpl()
        
        # Mock all dependencies
        with patch('render.services.render_service.repository') as mock_repo, \
             patch('render.services.render_service.query_executor') as mock_qe, \
             patch('render.services.render_service.template_renderer') as mock_tr, \
             patch('render.services.render_service.pdf_generator') as mock_pdf, \
             patch('render.services.render_service.AsyncSessionLocal') as mock_session:
            
            # Setup mocks
            mock_report = MagicMock()
            mock_repo.get_report.return_value = mock_report
            mock_qe.execute_queries = AsyncMock(return_value={"query": []})
            mock_tr.render.return_value = "<html>Test</html>"
            mock_pdf.generate = AsyncMock(return_value=b"%PDF-test")
            mock_storage = AsyncMock()
            mock_storage.save = AsyncMock(return_value="/path/to/pdf")
            service.storage = mock_storage
            
            # Mock database session
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
            mock_db.commit = AsyncMock()
            
            # Execute render
            result = await service.executeRender("test-report", {"param": "value"})
            
            # Verify workflow
            assert result.status == RenderStatus.COMPLETED
            assert result.pdf_bytes == b"%PDF-test"

    def test_hash_consistency_across_service_calls(self):
        """Test hash remains consistent across multiple service calls."""
        service = RenderServiceImpl()
        
        params = {"start_date": "2024-01-01", "end_date": "2024-12-31"}
        
        # Calculate hash multiple times through different methods
        hash1 = service._calculate_hash("report1", params)
        hash2 = service._calculate_hash("report1", params)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters
