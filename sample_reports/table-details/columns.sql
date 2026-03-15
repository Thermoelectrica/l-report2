-- Column information
SELECT
    ordinal_position as position,
    column_name,
    data_type,
    CASE
        WHEN character_maximum_length IS NOT NULL
        THEN data_type || '(' || character_maximum_length || ')'
        WHEN numeric_precision IS NOT NULL AND numeric_scale IS NOT NULL
        THEN data_type || '(' || numeric_precision || ',' || numeric_scale || ')'
        ELSE data_type
    END as full_type,
    is_nullable,
    column_default,
    CASE
        WHEN column_name IN (
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = (COALESCE(:schema_name, 'public') || '.' || :table_name)::regclass
              AND i.indisprimary
        ) THEN 'YES'
        ELSE 'NO'
    END as is_primary_key
FROM information_schema.columns
WHERE table_schema = COALESCE(:schema_name, 'public')
  AND table_name = :table_name
ORDER BY ordinal_position;
