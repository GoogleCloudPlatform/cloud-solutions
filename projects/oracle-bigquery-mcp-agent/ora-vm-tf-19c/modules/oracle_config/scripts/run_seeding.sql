-- Master Seeding Orchestration Script
@/tmp/seed_primary.sql
ALTER SESSION SET CONTAINER = ORCLPDB1;
@/tmp/app_setup.sql
EXIT;
