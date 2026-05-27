SELECT tablespace_name, round(used_percent, 2)
FROM dba_tablespace_usage_metrics
ORDER BY used_percent DESC
