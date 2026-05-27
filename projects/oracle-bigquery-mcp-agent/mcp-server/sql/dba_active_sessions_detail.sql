SELECT sid, serial#, username, program, last_call_et, wait_class
FROM v$session
WHERE status = 'ACTIVE' AND username IS NOT NULL
ORDER BY last_call_et DESC
FETCH FIRST 20 ROWS ONLY
