"""Tests for dynamic parameter and enum query dependency features."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from render.models import ParameterType, ReportMetadata, ReportParameter
from render.services.render_service import RenderServiceImpl
from render.services.query_executor import QueryExecutor


@pytest.fixture
def mock_query_executor():
    """Create a mock query executor."""
    executor = MagicMock(spec=QueryExecutor)
    executor.pool = MagicMock()  # Not None, so it's "initialized"
    executor._convert_default_value = QueryExecutor._convert_default_value.__get__(executor)
    return executor


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def sample_report_path(tmp_path):
    """Create a sample report directory with enum query files."""
    report_dir = tmp_path / "test-report"
    report_dir.mkdir()
    
    # Create schema_names_enum.sql (no parameters)
    schema_enum = report_dir / "schema_names_enum.sql"
    schema_enum.write_text("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schema_name;
    """)
    
    # Create table_names_enum.sql (depends on :schema_name)
    table_enum = report_dir / "table_names_enum.sql"
    table_enum.write_text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = COALESCE(:schema_name, 'public')
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    
    # Create column_names_enum.sql (depends on :schema_name and :table_name)
    column_enum = report_dir / "column_names_enum.sql"
    column_enum.write_text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = COALESCE(:schema_name, 'public')
        AND table_name = :table_name
        ORDER BY ordinal_position;
    """)
    
    return report_dir


class TestParseEnumQueryParams:
    """Test parsing parameter dependencies from SQL files."""
    
    def test_parse_no_parameters(self, tmp_path):
        """Test parsing SQL file with no parameters."""
        service = RenderServiceImpl()
        
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM users;")
        
        params = service._parse_enum_query_params(sql_file)
        assert params == []
    
    def test_parse_single_parameter(self, tmp_path):
        """Test parsing SQL file with one parameter."""
        service = RenderServiceImpl()
        
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM users WHERE id = :user_id;")
        
        params = service._parse_enum_query_params(sql_file)
        assert params == ["user_id"]
    
    def test_parse_multiple_parameters(self, tmp_path):
        """Test parsing SQL file with multiple parameters."""
        service = RenderServiceImpl()
        
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("""
            SELECT * FROM users 
            WHERE schema = :schema_name 
            AND table = :table_name
            AND active = :is_active;
        """)
        
        params = service._parse_enum_query_params(sql_file)
        assert set(params) == {"schema_name", "table_name", "is_active"}
    
    def test_parse_ignores_type_casts(self, tmp_path):
        """Test that PostgreSQL type casts (::type) are not parsed as parameters."""
        service = RenderServiceImpl()
        
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("""
            SELECT (:schema_name || '.' || :table_name)::regclass,
                   :count::integer,
                   :price::numeric(10,2);
        """)
        
        params = service._parse_enum_query_params(sql_file)
        # Should only find the named parameters, not the type casts
        assert set(params) == {"schema_name", "table_name", "count", "price"}
    
    def test_parse_duplicate_parameters(self, tmp_path):
        """Test that duplicate parameters are deduplicated."""
        service = RenderServiceImpl()
        
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("""
            SELECT * FROM users 
            WHERE name = :user_name 
            OR email LIKE :user_name || '%';
        """)
        
        params = service._parse_enum_query_params(sql_file)
        assert params == ["user_name"]


class TestGetParameterDependencies:
    """Test building parameter dependency graph."""
    
    @pytest.mark.asyncio
    async def test_no_dependencies(self, mock_query_executor, mock_repository):
        """Test report with no parameter dependencies."""
        service = RenderServiceImpl()
        
        # Mock metadata with no enum queries
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="param1",
                    type=ParameterType.STRING,
                    default="value1"
                )
            ]
        )
        
        with patch.object(service, 'getReportMetadata', return_value=metadata):
            deps = await service.getParameterDependencies("test-report")
            assert deps == {}
    
    @pytest.mark.asyncio
    async def test_simple_dependency(self, mock_query_executor, mock_repository):
        """Test simple one-to-one dependency."""
        service = RenderServiceImpl()
        
        # Mock metadata where table_name depends on schema_name
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="schema_name",
                    type=ParameterType.STRING,
                    default="public"
                ),
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql",
                    enum_query_params=["schema_name"]  # Depends on schema_name
                )
            ]
        )
        
        with patch.object(service, 'getReportMetadata', return_value=metadata):
            deps = await service.getParameterDependencies("test-report")
            assert deps == {"schema_name": ["table_name"]}
    
    @pytest.mark.asyncio
    async def test_multiple_dependencies(self, mock_query_executor, mock_repository):
        """Test parameter with multiple dependents."""
        service = RenderServiceImpl()
        
        # Mock metadata where both table_name and view_name depend on schema_name
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="schema_name",
                    type=ParameterType.STRING,
                    default="public"
                ),
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql",
                    enum_query_params=["schema_name"]
                ),
                ReportParameter(
                    name="view_name",
                    type=ParameterType.STRING,
                    enum_query="view_names_enum.sql",
                    enum_query_params=["schema_name"]
                )
            ]
        )
        
        with patch.object(service, 'getReportMetadata', return_value=metadata):
            deps = await service.getParameterDependencies("test-report")
            assert deps == {"schema_name": ["table_name", "view_name"]}
    
    @pytest.mark.asyncio
    async def test_chained_dependencies(self, mock_query_executor, mock_repository):
        """Test chained dependencies (A -> B -> C)."""
        service = RenderServiceImpl()
        
        # Mock metadata: schema_name -> table_name -> column_name
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="schema_name",
                    type=ParameterType.STRING,
                    default="public"
                ),
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql",
                    enum_query_params=["schema_name"]
                ),
                ReportParameter(
                    name="column_name",
                    type=ParameterType.STRING,
                    enum_query="column_names_enum.sql",
                    enum_query_params=["schema_name", "table_name"]
                )
            ]
        )
        
        with patch.object(service, 'getReportMetadata', return_value=metadata):
            deps = await service.getParameterDependencies("test-report")
            assert deps == {
                "schema_name": ["table_name", "column_name"],
                "table_name": ["column_name"]
            }


class TestRefreshEnumValues:
    """Test refreshing enum values based on parameter changes."""
    
    @pytest.mark.asyncio
    async def test_refresh_with_parameters(self, mock_query_executor, mock_repository, sample_report_path):
        """Test refreshing enum values with current parameters."""
        service = RenderServiceImpl()
        
        # Mock report
        mock_report = MagicMock()
        mock_report.path = sample_report_path
        
        # Mock metadata
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="schema_name",
                    type=ParameterType.STRING,
                    default="public"
                ),
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql"
                )
            ]
        )
        
        # Mock query executor to return table names
        mock_query_executor.execute_enum_query = AsyncMock(
            return_value=["users", "orders", "products"]
        )
        
        with patch('render.services.render_service.repository.get_report', return_value=mock_report), \
             patch('render.services.render_service.repository.get_metadata', return_value=metadata), \
             patch('render.services.render_service.query_executor', mock_query_executor):
            
            current_params = {"schema_name": "myschema", "table_name": None}
            enum_values = await service.refreshEnumValues(
                "test-report",
                "table_name",
                current_params
            )
            
            assert enum_values == ["users", "orders", "products"]
            mock_query_executor.execute_enum_query.assert_called_once()
            call_args = mock_query_executor.execute_enum_query.call_args
            assert call_args[0][1] == current_params  # Verify parameters were passed
    
    @pytest.mark.asyncio
    async def test_refresh_nonexistent_parameter(self, mock_query_executor, mock_repository, sample_report_path):
        """Test refreshing enum for non-existent parameter."""
        service = RenderServiceImpl()
        
        mock_report = MagicMock()
        mock_report.path = sample_report_path
        
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[]
        )
        
        with patch('render.services.render_service.repository.get_report', return_value=mock_report), \
             patch('render.services.render_service.repository.get_metadata', return_value=metadata):
            
            enum_values = await service.refreshEnumValues(
                "test-report",
                "nonexistent_param",
                {}
            )
            
            assert enum_values == []
    
    @pytest.mark.asyncio
    async def test_refresh_parameter_without_enum_query(self, mock_query_executor, mock_repository, sample_report_path):
        """Test refreshing enum for parameter without enum_query."""
        service = RenderServiceImpl()
        
        mock_report = MagicMock()
        mock_report.path = sample_report_path
        
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="param1",
                    type=ParameterType.STRING,
                    # No enum_query
                )
            ]
        )
        
        with patch('render.services.render_service.repository.get_report', return_value=mock_report), \
             patch('render.services.render_service.repository.get_metadata', return_value=metadata):
            
            enum_values = await service.refreshEnumValues(
                "test-report",
                "param1",
                {}
            )
            
            assert enum_values == []
    
    @pytest.mark.asyncio
    async def test_refresh_handles_query_error(self, mock_query_executor, mock_repository, sample_report_path):
        """Test that refresh handles query execution errors gracefully."""
        service = RenderServiceImpl()
        
        mock_report = MagicMock()
        mock_report.path = sample_report_path
        
        metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql"
                )
            ]
        )
        
        # Mock query executor to raise an error
        mock_query_executor.execute_enum_query = AsyncMock(
            side_effect=RuntimeError("Database connection failed")
        )
        
        with patch('render.services.render_service.repository.get_report', return_value=mock_report), \
             patch('render.services.render_service.repository.get_metadata', return_value=metadata), \
             patch('render.services.render_service.query_executor', mock_query_executor):
            
            # Should return empty list instead of raising
            enum_values = await service.refreshEnumValues(
                "test-report",
                "table_name",
                {"schema_name": "public"}
            )
            
            assert enum_values == []


class TestGetReportMetadataWithDependencies:
    """Test getReportMetadata with enum_query_params parsing."""
    
    @pytest.mark.asyncio
    async def test_metadata_includes_enum_query_params(self, mock_query_executor, mock_repository, sample_report_path):
        """Test that getReportMetadata populates enum_query_params."""
        service = RenderServiceImpl()
        
        # Mock report
        mock_report = MagicMock()
        mock_report.path = sample_report_path
        
        # Base metadata without enum_query_params
        base_metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="schema_name",
                    type=ParameterType.STRING,
                    default="public",
                    enum_query="schema_names_enum.sql"
                ),
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql"
                )
            ]
        )
        
        # Mock query executor
        mock_query_executor.execute_enum_query = AsyncMock(
            return_value=["value1", "value2"]
        )
        
        with patch('render.services.render_service.repository.get_metadata', return_value=base_metadata), \
             patch('render.services.render_service.repository.get_report', return_value=mock_report), \
             patch('render.services.render_service.query_executor', mock_query_executor):
            
            metadata = await service.getReportMetadata("test-report")
            
            # Check that enum_query_params were parsed
            assert metadata.parameters[0].enum_query_params == []  # schema_names_enum has no params
            assert metadata.parameters[1].enum_query_params == ["schema_name"]  # table_names_enum depends on schema_name
    
    @pytest.mark.asyncio
    async def test_metadata_executes_enum_queries_with_defaults(self, mock_query_executor, mock_repository, sample_report_path):
        """Test that enum queries are executed with default parameter values."""
        service = RenderServiceImpl()
        
        mock_report = MagicMock()
        mock_report.path = sample_report_path
        
        base_metadata = ReportMetadata(
            id="test-report",
            name="Test Report",
            format="weasyprint",
            parameters=[
                ReportParameter(
                    name="schema_name",
                    type=ParameterType.STRING,
                    default="myschema"
                ),
                ReportParameter(
                    name="table_name",
                    type=ParameterType.STRING,
                    enum_query="table_names_enum.sql"
                )
            ]
        )
        
        mock_query_executor.execute_enum_query = AsyncMock(
            return_value=["table1", "table2"]
        )
        
        with patch('render.services.render_service.repository.get_metadata', return_value=base_metadata), \
             patch('render.services.render_service.repository.get_report', return_value=mock_report), \
             patch('render.services.render_service.query_executor', mock_query_executor):
            
            metadata = await service.getReportMetadata("test-report")
            
            # Verify enum query was called with default values
            mock_query_executor.execute_enum_query.assert_called()
            call_args = mock_query_executor.execute_enum_query.call_args
            params_passed = call_args[0][1]
            assert params_passed["schema_name"] == "myschema"
            
            # Verify enum values were populated
            assert metadata.parameters[1].enum == ["table1", "table2"]
