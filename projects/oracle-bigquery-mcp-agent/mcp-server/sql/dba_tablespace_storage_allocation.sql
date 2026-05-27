SELECT df.tablespace_name,
       ROUND(((df.bytes - NVL(fs.bytes, 0)) / df.bytes) * 100) AS used_percent
FROM (SELECT tablespace_name, SUM(bytes) AS bytes FROM dba_data_files GROUP BY tablespace_name) df,
     (SELECT tablespace_name, SUM(bytes) AS bytes FROM dba_free_space GROUP BY tablespace_name) fs
WHERE df.tablespace_name = fs.tablespace_name
ORDER BY used_percent DESC
