SELECT i.instance_name, i.status, d.database_role, i.host_name,
       (SELECT banner FROM v$version WHERE ROWNUM = 1) AS banner,
       TO_CHAR(i.startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time
FROM v$instance i
CROSS JOIN v$database d
