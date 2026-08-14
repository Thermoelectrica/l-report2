"""Tests for dynamic parameter and enum query dependency features."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from render.models import ParameterType, ReportMetadata, ReportParameter
from render.services.render_service import RenderServiceImpl
from render.services.query_executor import QueryExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_executor() -> QueryExecutor:
    """Return a QueryExecutor instance with a fake (non-None) pool."""
    executor = QueryExecutor.__new__(QueryExecutor)
    executor.pool = MagicMock()  # not None → passes the guard check
    return executor


def _make_metadata(*params: ReportParameter) -> ReportMetadata:
    return ReportMetadata(
        id="test", name="Test", format="weasyprint", parameters=list(params)
    )


def _param(name: str, ptype: ParameterType = ParameterType.STRING, **kw) -> ReportParameter:
    return ReportParameter(name=name, type=ptype, **kw)


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


# ---------------------------------------------------------------------------
# Tests for duplicate named-parameter handling and type-cast generation
# (regression for asyncpg.exceptions.AmbiguousParameterError)
# ---------------------------------------------------------------------------

class TestConvertNamedToPositionalDuplicates:
    """
    Verify that _convert_named_to_positional correctly handles queries where
    the same named parameter appears more than once (e.g. in an IS NULL guard).

    Before the fix, such queries produced a bare ``$1`` in contexts like
    ``$1 IS NULL``, causing PostgreSQL to raise
    ``AmbiguousParameterError: could not determine data type of parameter $1``.

    After the fix every placeholder is emitted with an explicit type cast
    (e.g. ``$1::text``), so PostgreSQL always knows the type.
    """

    def test_duplicate_param_produces_single_positional_slot(self):
        """Same name used twice → only one entry in positional_params."""
        executor = _make_executor()
        metadata = _make_metadata(_param("plant_name"))

        query = "SELECT * FROM t WHERE col = :plant_name OR :plant_name IS NULL"
        converted, params = executor._convert_named_to_positional(
            query, {"plant_name": "Acme"}, metadata
        )

        # Only one value in the positional list
        assert params == ["Acme"]
        # Both occurrences replaced with $1
        assert "$1" in converted
        assert ":plant_name" not in converted

    def test_duplicate_param_gets_type_cast(self):
        """Every $N placeholder must carry a type cast to avoid AmbiguousParameterError."""
        executor = _make_executor()
        metadata = _make_metadata(_param("plant_name", ParameterType.STRING))

        query = "SELECT * FROM t WHERE col = :plant_name OR :plant_name IS NULL"
        converted, _ = executor._convert_named_to_positional(
            query, {"plant_name": "Acme"}, metadata
        )

        # Both occurrences must have the cast appended
        import re
        placeholders = re.findall(r"\$1[^\d]", converted + " ")  # avoid matching $10
        assert all("::text" in p or converted.count("$1::text") == 2 for p in placeholders), (
            f"Expected $1::text in both occurrences, got: {converted!r}"
        )
        assert converted.count("$1::text") == 2

    def test_type_cast_for_integer_param(self):
        """Integer parameters get ::integer cast."""
        executor = _make_executor()
        metadata = _make_metadata(_param("limit_val", ParameterType.INTEGER))

        query = "SELECT * FROM t WHERE id < :limit_val OR :limit_val IS NULL"
        converted, params = executor._convert_named_to_positional(
            query, {"limit_val": 42}, metadata
        )

        assert params == [42]
        assert converted.count("$1::integer") == 2

    def test_type_cast_for_date_param(self):
        """Date parameters get ::date cast."""
        from datetime import date
        executor = _make_executor()
        metadata = _make_metadata(_param("start_date", ParameterType.DATE))

        d = date(2024, 1, 1)
        query = "SELECT * FROM t WHERE dt >= :start_date OR :start_date IS NULL"
        converted, params = executor._convert_named_to_positional(
            query, {"start_date": d}, metadata
        )

        assert params == [d]
        assert converted.count("$1::date") == 2

    def test_type_cast_for_boolean_param(self):
        """Boolean parameters get ::boolean cast."""
        executor = _make_executor()
        metadata = _make_metadata(_param("is_active", ParameterType.BOOLEAN))

        query = "SELECT * FROM t WHERE active = :is_active OR :is_active IS NULL"
        converted, params = executor._convert_named_to_positional(
            query, {"is_active": True}, metadata
        )

        assert params == [True]
        assert converted.count("$1::boolean") == 2

    def test_type_cast_for_float_param(self):
        """Float parameters get ::double precision cast."""
        executor = _make_executor()
        metadata = _make_metadata(_param("price", ParameterType.FLOAT))

        query = "SELECT * FROM t WHERE price > :price OR :price IS NULL"
        converted, params = executor._convert_named_to_positional(
            query, {"price": 9.99}, metadata
        )

        assert params == [9.99]
        assert "$1::double precision" in converted

    def test_type_cast_unknown_param_falls_back_to_text(self):
        """Parameter not in metadata gets ::text cast as safe fallback."""
        executor = _make_executor()
        # metadata has no parameters defined
        metadata = _make_metadata()

        query = "SELECT * FROM t WHERE col = :mystery OR :mystery IS NULL"
        # mystery is not required (not in metadata), value provided explicitly
        converted, params = executor._convert_named_to_positional(
            query, {"mystery": "hello"}, metadata
        )

        assert params == ["hello"]
        assert converted.count("$1::text") == 2

    def test_multiple_distinct_params_each_get_cast(self):
        """Multiple distinct parameters each get their own cast."""
        executor = _make_executor()
        metadata = _make_metadata(
            _param("schema_name", ParameterType.STRING),
            _param("table_name", ParameterType.STRING),
        )

        query = (
            "SELECT * FROM t "
            "WHERE schema = :schema_name AND tbl = :table_name "
            "OR :schema_name IS NULL OR :table_name IS NULL"
        )
        converted, params = executor._convert_named_to_positional(
            query,
            {"schema_name": "public", "table_name": "users"},
            metadata,
        )

        assert params == ["public", "users"]
        assert converted.count("$1::text") == 2  # schema_name appears twice
        assert converted.count("$2::text") == 2  # table_name appears twice

    def test_existing_pg_type_cast_in_query_not_double_cast(self):
        """
        If the SQL already contains a ::cast on the named param (e.g. :val::text),
        the replacement must not produce $1::text::text.
        """
        executor = _make_executor()
        metadata = _make_metadata(_param("val", ParameterType.STRING))

        # User wrote an explicit cast in the SQL
        query = "SELECT :val::text AS v"
        converted, params = executor._convert_named_to_positional(
            query, {"val": "hello"}, metadata
        )

        assert params == ["hello"]
        # Should not contain double cast
        assert "::text::text" not in converted
