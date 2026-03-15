-- Table statistics with row counts
SELECT 
    schemaname as schema_name,
    relname as table_name,
    n_live_tup as estimated_rows,
    n_dead_tup as dead_rows,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = COALESCE($1, 'public')
ORDER BY n_live_tup DESC;
