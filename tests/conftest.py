"""Shared pytest fixtures for all tests."""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from render.database.models import Base, Render
from render.models import (
    ReportMetadata,
    ReportParameter,
    ParameterType,
    ReportListItem,
    RenderStatus,
)
from render.services.repository import Report


# ============================================================================
# Async Event Loop Fixture
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
async def test_db_engine():
    """Create in-memory SQLite database engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_reports_dir(temp_dir: Path) -> Path:
    """Create temporary reports directory with sample structure."""
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir()
    return reports_dir


@pytest.fixture
def temp_storage_dir(temp_dir: Path) -> Path:
    """Create temporary storage directory for PDFs."""
    storage_dir = temp_dir / "storage"
    storage_dir.mkdir()
    return storage_dir


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_report_metadata() -> ReportMetadata:
    """Create sample report metadata."""
    return ReportMetadata(
        id="test-report",
        name="Test Report",
        description="A test report for unit testing",
        version="1.0",
        timeout=60,
        parameters=[
            ReportParameter(
                name="start_date",
                type=ParameterType.DATE,
                required=True,
                description="Start date for the report",
            ),
            ReportParameter(
                name="end_date",
                type=ParameterType.DATE,
                required=True,
                description="End date for the report",
            ),
            ReportParameter(
                name="schema_name",
                type=ParameterType.STRING,
                required=False,
                description="Database schema",
                default="public",
            ),
        ],
    )


@pytest.fixture
def sample_parameters() -> dict:
    """Create sample parameters for testing."""
    return {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "schema_name": "public",
    }


@pytest.fixture
def sample_query_results() -> dict:
    """Create sample query results as list of dictionaries."""
    return {
        "tables_list": [
            {"schema_name": "public", "table_name": "users", "total_size": "1 MB"},
            {"schema_name": "public", "table_name": "orders", "total_size": "5 MB"},
        ],
        "table_stats": [
            {"table_name": "users", "row_count": 100},
            {"table_name": "orders", "row_count": 500},
        ],
    }


@pytest.fixture
def sample_html() -> str:
    """Create sample HTML for PDF generation."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Report</title>
        <style>
            body { font-family: Arial, sans-serif; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
        </style>
    </head>
    <body>
        <h1>Test Report</h1>
        <table>
            <tr><th>Column 1</th><th>Column 2</th></tr>
            <tr><td>Data 1</td><td>Data 2</td></tr>
        </table>
    </body>
    </html>
    """


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Create sample PDF bytes (minimal valid PDF)."""
    # Minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
409
%%EOF
"""


# ============================================================================
# Mock Report Fixtures
# ============================================================================

@pytest.fixture
def mock_report(sample_report_metadata: ReportMetadata, temp_reports_dir: Path) -> Report:
    """Create mock Report object with files."""
    report_dir = temp_reports_dir / "test-report"
    report_dir.mkdir()
    
    # Create metadata.yaml
    metadata_file = report_dir / "metadata.yaml"
    metadata_file.write_text("""
name: "Test Report"
description: "A test report"
version: "1.0"
timeout: 60
parameters:
  - name: start_date
    type: date
    required: true
    description: "Start date"
  - name: end_date
    type: date
    required: true
    description: "End date"
  - name: schema_name
    type: string
    required: false
    description: "Schema name"
    default: "public"
""")
    
    # Create template
    template_file = report_dir / "index.html.j2"
    template_file.write_text("""
<!DOCTYPE html>
<html>
<head><title>{{ globals.report_name }}</title></head>
<body>
    <h1>{{ globals.report_name }}</h1>
    <p>Generated: {{ globals.generated_at }}</p>
    <p>Start: {{ params.start_date }}, End: {{ params.end_date }}</p>
    {% for row in queries.test_query %}
    <p>{{ row.name }}</p>
    {% endfor %}
</body>
</html>
""")
    
    # Create SQL query
    query_file = report_dir / "test_query.sql"
    query_file.write_text("SELECT 'test' as name;")
    
    return Report(report_dir, sample_report_metadata)


# ============================================================================
# Database Record Fixtures
# ============================================================================

@pytest.fixture
async def sample_render_record(db_session: AsyncSession) -> Render:
    """Create sample render record in database."""
    render = Render(
        parameter_hash="abc123def456",
        report_id="test-report",
        parameters_json='{"start_date": "2024-01-01", "end_date": "2024-12-31"}',
        status=RenderStatus.PENDING.value,
    )
    db_session.add(render)
    await db_session.commit()
    await db_session.refresh(render)
    return render


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_query_executor():
    """Create mock query executor."""
    mock = AsyncMock()
    mock.execute_queries = AsyncMock(return_value={
        "test_query": [{"name": "test"}]
    })
    return mock


@pytest.fixture
def mock_template_renderer():
    """Create mock template renderer."""
    mock = MagicMock()
    mock.render = MagicMock(return_value="<html><body>Test</body></html>")
    return mock


@pytest.fixture
def mock_pdf_generator():
    """Create mock PDF generator."""
    mock = AsyncMock()
    mock.generate = AsyncMock(return_value=b"%PDF-1.4 test")
    return mock


@pytest.fixture
def mock_storage():
    """Create mock storage backend."""
    mock = AsyncMock()
    mock.save = AsyncMock(return_value="/path/to/test.pdf")
    mock.retrieve = AsyncMock(return_value=b"%PDF-1.4 test")
    mock.exists = AsyncMock(return_value=True)
    mock.delete = AsyncMock()
    return mock
