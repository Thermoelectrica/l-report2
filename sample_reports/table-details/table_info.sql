-- Basic table information
SELECT
    schemaname as schema_name,
    tablename as table_name,
    tableowner as owner,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size
FROM pg_tables
WHERE schemaname = COALESCE(:schema_name, 'public')
  AND tablename = :table_name;
