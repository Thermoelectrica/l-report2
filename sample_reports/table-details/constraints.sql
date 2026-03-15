-- Constraint information
SELECT
    conname as constraint_name,
    CASE contype
        WHEN 'p' THEN 'PRIMARY KEY'
        WHEN 'f' THEN 'FOREIGN KEY'
        WHEN 'u' THEN 'UNIQUE'
        WHEN 'c' THEN 'CHECK'
        ELSE contype::text
    END as constraint_type,
    pg_get_constraintdef(c.oid) as definition
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
JOIN pg_class cl ON cl.oid = c.conrelid
WHERE n.nspname = COALESCE(:schema_name, 'public')
  AND cl.relname = :table_name
ORDER BY
    CASE contype
        WHEN 'p' THEN 1
        WHEN 'u' THEN 2
        WHEN 'f' THEN 3
        WHEN 'c' THEN 4
        ELSE 5
    END,
    conname;
