SELECT sid, username, event, last_call_et
FROM v$session
WHERE username IS NOT NULL AND status = 'ACTIVE'
FETCH FIRST 4 ROWS ONLY
