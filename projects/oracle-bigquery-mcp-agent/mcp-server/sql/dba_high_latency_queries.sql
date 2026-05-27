SELECT sql_id, round(elapsed_time/1000000, 2), substr(sql_text, 1, 40)
FROM v$sql
ORDER BY elapsed_time DESC
FETCH FIRST 20 ROWS ONLY
