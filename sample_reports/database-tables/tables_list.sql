-- List all tables with metadata
SELECT
    schemaname as schema_name,
    tablename as table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size
FROM pg_tables
WHERE schemaname = COALESCE(:schema_name, 'public')
ORDER BY
    pg_total_relation_size(schemaname||'.'||tablename) DESC;
