SELECT owner, object_name, object_type
FROM all_objects
WHERE status = 'INVALID'
FETCH FIRST 20 ROWS ONLY
