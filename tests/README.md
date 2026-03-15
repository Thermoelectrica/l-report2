# Test Suite Documentation

Comprehensive test suite for the PDF Report Renderer service.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── test_models.py           # Unit tests for Pydantic models
├── test_repository.py       # Unit tests for report repository
├── test_storage.py          # Unit tests for storage backends
├── test_render_service.py   # Unit tests for render service
└── test_integration.py      # Integration tests for complete workflows
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_models.py
pytest tests/test_repository.py
```

### Run Specific Test Class

```bash
pytest tests/test_models.py::TestReportMetadata
```

### Run Specific Test

```bash
pytest tests/test_models.py::TestReportMetadata::test_create_full_metadata
```

### Run with Coverage

```bash
pytest --cov=render --cov-report=html
```

View coverage report: `open htmlcov/index.html`

### Run Only Unit Tests (exclude integration)

```bash
pytest -m "not integration"
```

### Run Only Integration Tests

```bash
pytest -m integration
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Output Capture Disabled

```bash
pytest -s
```

## Test Categories

### Unit Tests

**test_models.py** - Tests for Pydantic data models
- `TestReportListItem` - Report list item validation
- `TestReportParameter` - Parameter definition validation
- `TestReportMetadata` - Report metadata validation
- `TestRenderStatus` - Status enum tests
- `TestRenderResult` - Render result model tests

**test_repository.py** - Tests for report repository
- `TestReportRepository` - Repository loading and management
- `TestReport` - Report object properties

**test_storage.py** - Tests for storage backends
- `TestFilesystemStorage` - Filesystem storage operations

**test_render_service.py** - Tests for render service
- `TestRenderServiceImpl` - Core service functionality
- `TestRenderServiceIntegration` - Service integration scenarios

### Integration Tests

**test_integration.py** - End-to-end workflow tests
- `TestReportWorkflow` - Complete report rendering workflows
- `TestEndToEndScenarios` - Real-world usage scenarios

## Fixtures

### Database Fixtures

- `test_db_engine` - In-memory SQLite database engine
- `db_session` - Database session for testing
- `sample_render_record` - Pre-populated render record

### File System Fixtures

- `temp_dir` - Temporary directory for tests
- `temp_reports_dir` - Temporary reports directory
- `temp_storage_dir` - Temporary storage directory

### Data Fixtures

- `sample_report_metadata` - Sample ReportMetadata object
- `sample_parameters` - Sample parameter dictionary
- `sample_query_results` - Sample query results as DataFrames
- `sample_html` - Sample HTML content
- `sample_pdf_bytes` - Sample PDF bytes

### Mock Fixtures

- `mock_report` - Mock Report object with files
- `mock_query_executor` - Mock query executor
- `mock_template_renderer` - Mock template renderer
- `mock_pdf_generator` - Mock PDF generator
- `mock_storage` - Mock storage backend

## Test Coverage Goals

- **Models**: 100% coverage
- **Repository**: 95%+ coverage
- **Storage**: 95%+ coverage
- **Services**: 90%+ coverage
- **Integration**: Key workflows covered

## Writing New Tests

### Example Unit Test

```python
def test_my_feature(sample_report_metadata):
    """Test description."""
    # Arrange
    metadata = sample_report_metadata
    
    # Act
    result = some_function(metadata)
    
    # Assert
    assert result.id == "test-report"
```

### Example Async Test

```python
@pytest.mark.asyncio
async def test_async_feature(db_session):
    """Test async functionality."""
    # Arrange
    data = {"key": "value"}
    
    # Act
    result = await async_function(db_session, data)
    
    # Assert
    assert result is not None
```

### Example Integration Test

```python
@pytest.mark.integration
def test_complete_workflow(temp_reports_dir):
    """Test complete workflow."""
    # Create test data
    setup_test_report(temp_reports_dir)
    
    # Execute workflow
    result = execute_workflow()
    
    # Verify results
    assert result.status == "completed"
```

## Best Practices

1. **Use Fixtures** - Leverage shared fixtures for common setup
2. **Clear Names** - Test names should describe what they test
3. **AAA Pattern** - Arrange, Act, Assert structure
4. **One Assertion** - Focus each test on one behavior
5. **Isolation** - Tests should not depend on each other
6. **Cleanup** - Use fixtures for automatic cleanup
7. **Mocking** - Mock external dependencies
8. **Documentation** - Add docstrings to complex tests

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=render --cov-report=xml
```

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Install dependencies
pip install -r requirements.txt
```

### Async Tests Not Running

```bash
# Install pytest-asyncio
pip install pytest-asyncio
```

### Database Tests Fail

```bash
# Install aiosqlite for in-memory testing
pip install aiosqlite
```

## Performance

- Unit tests: < 1 second total
- Integration tests: < 5 seconds total
- Full suite: < 10 seconds total

## Future Enhancements

- [ ] Add performance benchmarks
- [ ] Add mutation testing
- [ ] Add property-based testing with Hypothesis
- [ ] Add contract testing for API
- [ ] Add load testing scenarios
