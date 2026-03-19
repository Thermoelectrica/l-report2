-- Query to fetch list of schema names for enum dropdown
SELECT 
    schema_name
FROM 
    information_schema.schemata
WHERE 
    schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
ORDER BY 
    schema_name;
