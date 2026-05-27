-- Enable Archive Log Mode and supplemental logging for Datastream CDC
SHUTDOWN IMMEDIATE;
STARTUP MOUNT;
ALTER DATABASE ARCHIVELOG;
ALTER DATABASE OPEN;
ALTER PLUGGABLE DATABASE ALL OPEN;
ALTER SYSTEM SWITCH LOGFILE;

ALTER DATABASE ADD SUPPLEMENTAL LOG DATA;
ALTER DATABASE ADD SUPPLEMENTAL LOG DATA (ALL) COLUMNS;



-- ============================================================================
-- 5. FINAL VALIDATION
-- ============================================================================
COLUMN name FORMAT A15;
SELECT name, open_mode FROM v$pdbs;

PROMPT Primary Seed Configuration Complete.
