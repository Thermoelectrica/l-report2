# PDF Report Renderer

A flexible PDF report generation service that executes SQL queries and renders them as beautiful PDF documents using Jinja2 templates.

## Features

- 📊 **SQL-based Reports**: Define reports with SQL queries and Jinja2 templates
- 🎨 **Beautiful PDFs**: Generate professional PDFs with WeasyPrint
- ⚡ **Smart Caching**: Configurable cache (default 5 minutes) with per-report overrides
- 🔄 **Background Processing**: Async rendering with status polling
- 💾 **Flexible Storage**: Filesystem or S3-compatible storage
- 🖼️ **S3 Image Support**: Presigned URLs for images in reports

## Architecture

### Report Structure

Each report is a folder in `REPORTS_PATH` containing:

```
sample_reports/
├── database-tables/
│   ├── metadata.yaml       # Report definition
│   ├── index.html.j2       # Jinja2 template
│   ├── tables_list.sql     # SQL query
│   └── table_stats.sql     # Another SQL query
└── table-details/
    ├── metadata.yaml
    ├── index.html.j2
    ├── table_info.sql
    ├── columns.sql
    └── ...
```

### metadata.yaml

```yaml
name: "Database Tables Report"
description: "List all tables in the database"
version: "1.0"
timeout: 120
cache_ttl_minutes: 10  # Optional: Override global cache TTL (default: 5 minutes)

parameters:
  - name: schema_name
    type: string
    required: false
    description: "Filter by schema"
    default: "public"
```

### SQL Queries

Use named parameters with `:param_name` syntax:

```sql
SELECT * FROM pg_tables
WHERE schemaname = COALESCE(:schema_name, 'public')
ORDER BY tablename;
```

### Jinja2 Templates

Access query results, parameters, and globals:

```html
<h1>{{ globals.report_name }}</h1>
<p>Schema: {{ params.schema_name }}</p>

<table>
  {% for row in queries.tables_list %}
  <tr>
    <td>{{ row.table_name }}</td>
    <td>{{ row.total_size }}</td>
  </tr>
  {% endfor %}
</table>
```

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment (copy `.env.example` to `.env`):

```bash
# Report Repository
REPORTS_PATH=./sample_reports

# Data Database (for queries)
DATA_DB_HOST=localhost
DATA_DB_PORT=5432
DATA_DB_NAME=postgres
DATA_DB_USER=user
DATA_DB_PASSWORD=password

# Metadata Database (for render tracking)
META_DB_HOST=localhost
META_DB_PORT=5432
META_DB_NAME=postgres
META_DB_USER=user
META_DB_PASSWORD=password

# Storage
STORAGE_BACKEND=filesystem
STORAGE_PATH=./output/pdfs
```

3. Initialize database:

```bash
python -m render.main
```

## Usage

### Python API

```python
from render import render_service, init_db, query_executor
import asyncio

async def main():
    # Initialize
    await init_db()
    await query_executor.initialize()
    
    # List available reports
    reports = render_service.listReports()
    for report in reports:
        print(f"{report.id}: {report.name}")
    
    # Get report metadata
    metadata = render_service.getReportMetadata("database-tables")
    print(f"Parameters: {[p.name for p in metadata.parameters]}")
    
    # Start rendering
    render_service.startRender(
        "database-tables",
        {"schema_name": "public"},
        force_refresh=False
    )
    
    # Poll status
    while True:
        result = render_service.getRenderStatus(
            "database-tables",
            {"schema_name": "public"}
        )
        
        if result.status == RenderStatus.COMPLETED:
            # Save PDF
            with open("report.pdf", "wb") as f:
                f.write(result.pdf_bytes)
            break
        elif result.status == RenderStatus.FAILED:
            print(f"Error: {result.error_message}")
            break
        
        await asyncio.sleep(1)

asyncio.run(main())
```

### Contract Interface

The service implements the `RenderService` interface:

```python
class RenderService(ABC):
    def listReports() -> List[ReportListItem]
    def getReportMetadata(report_id: str) -> ReportMetadata
    def startRender(report_id: str, params: Dict[str, Any], force_refresh: bool = False) -> None
    def getRenderStatus(report_id: str, params: Dict[str, Any]) -> RenderResult
```

## Caching

Reports are cached using SHA256 hash of `{report_id, parameters}`:

- **Cache Key**: `sha256(json.dumps({"report_id": "...", "parameters": {...}}))`
- **Global TTL**: 5 minutes (configurable via `CACHE_TTL_MINUTES` environment variable)
- **Per-Report TTL**: Override global TTL by setting `cache_ttl_minutes` in `metadata.yaml`
- **Force Refresh**: Use `force_refresh=True` to bypass cache

### Cache Configuration

Set global cache TTL in `.env`:
```bash
CACHE_TTL_MINUTES=5  # Default: 5 minutes
```

Override for specific reports in `metadata.yaml`:
```yaml
name: "My Report"
cache_ttl_minutes: 60  # Cache this report for 1 hour
```

## Database Schema

The metadata database tracks render jobs:

```sql
CREATE TABLE renders (
    parameter_hash VARCHAR(64) PRIMARY KEY,  -- SHA256 hash
    report_id VARCHAR(255) NOT NULL,
    parameters_json TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,             -- PENDING/RUNNING/COMPLETED/FAILED
    pdf_path VARCHAR(512),
    file_size_bytes INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

## Storage Backends

### Filesystem (default)

```bash
STORAGE_BACKEND=filesystem
STORAGE_PATH=./output/pdfs
```

### S3-Compatible

```bash
STORAGE_BACKEND=s3
S3_BUCKET=my-reports-bucket
S3_ENDPOINT=https://storage.yandexcloud.net
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

## Custom Jinja2 Filters

Available in templates:

- `{{ value | format_number }}` - Format numbers with commas
- `{{ date | format_date }}` - Format dates as YYYY-MM-DD
- `{{ datetime | format_datetime }}` - Format datetime
- `{{ path | image_url }}` - Generate S3 presigned URLs for images

## Sample Reports

### database-tables

Lists all tables in a schema with sizes and statistics.

**Parameters:**
- `schema_name` (string, optional): Schema to filter (default: "public")

### table-details

Detailed analysis of a specific table.

**Parameters:**
- `schema_name` (string, optional): Schema name (default: "public")
- `table_name` (string, required): Table to analyze

## Development

Run the example:

```bash
python -m render.main
```

This will:
1. Initialize database and services
2. List available reports
3. Show metadata for the first report

## License

MIT
