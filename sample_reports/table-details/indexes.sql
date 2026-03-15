-- Index information
SELECT
    indexname as index_name,
    indexdef as definition,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) as index_size
FROM pg_indexes
WHERE schemaname = COALESCE(:schema_name, 'public')
  AND tablename = :table_name
ORDER BY indexname;
