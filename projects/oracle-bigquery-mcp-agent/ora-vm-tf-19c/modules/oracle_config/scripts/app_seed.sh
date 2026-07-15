#!/usr/bin/env bash

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ========================================================================================
# FYNANCEAI: ORACLE 19C SQL DATABASE SEEDING & USER PROVISIONING
# Dynamically runs sqlplus configurations for replication & application schemas
# ========================================================================================
set -euo pipefail

DB_PASSWORD="${1:-}"
if [ -z "$DB_PASSWORD" ]; then
  # Try to access Secret Manager version if password parameter is omitted
  DB_PASSWORD=$(gcloud secrets versions access latest --secret="oracle-db-password" 2>/dev/null || echo "")
  if [ -z "$DB_PASSWORD" ]; then
    echo "Error: Database password not provided and Secret Manager lookup failed."
    exit 1
  fi
fi

echo "1. Resolving local Oracle VM network configurations..."
INTERNAL_IP=$(ip route get 1 | awk '{print $7;exit}')
echo "Using Internal IP: $INTERNAL_IP"

# Replace placeholder in primary SQL schema
if [ -f "/tmp/seed_primary.sql" ]; then
  sed -i "s/YOUR_VM_INTERNAL_IP/$INTERNAL_IP/g" /tmp/seed_primary.sql
fi

echo "2. Loading Oracle database environment variables..."
export ORACLE_HOME=/opt/oracle/product/19c/dbhome_1
export ORACLE_SID=ORCLCDB
export PATH=$ORACLE_HOME/bin:$PATH

echo "3. Executing sysdba sqlplus commands..."
# Running @/tmp/seed_primary.sql inside the heredoc allows SQL*Plus to execute CDB/PDB archive configurations
# without prematurely closing the standard input stream before subsequent schema/CDC setups.
sqlplus / as sysdba <<EOF
@/tmp/seed_primary.sql

-- 1. Configure global Datastream CDC replication user container-wide
DECLARE
  u_exists EXCEPTION;
  PRAGMA EXCEPTION_INIT(u_exists, -1920);
BEGIN
  EXECUTE IMMEDIATE 'CREATE USER c##datastream IDENTIFIED BY "${DB_PASSWORD}" CONTAINER=ALL';
EXCEPTION
  WHEN u_exists THEN
    EXECUTE IMMEDIATE 'ALTER USER c##datastream IDENTIFIED BY "${DB_PASSWORD}"';
END;
/

GRANT CREATE SESSION, SET CONTAINER, SELECT ANY TABLE, SELECT ANY TRANSACTION, SELECT ANY DICTIONARY, LOGMINING, EXECUTE_CATALOG_ROLE, SELECT_CATALOG_ROLE TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$DATABASE TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$ARCHIVED_LOG TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$LOG TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$LOGFILE TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$LOGMNR_CONTENTS TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$LOGMNR_DICTIONARY TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$LOGMNR_LOGS TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$LOGMNR_PARAMETERS TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.V_\$PARAMETER TO c##datastream CONTAINER=ALL;
GRANT EXECUTE ON SYS.DBMS_LOGMNR TO c##datastream CONTAINER=ALL;
GRANT EXECUTE ON SYS.DBMS_LOGMNR_D TO c##datastream CONTAINER=ALL;
GRANT SELECT ON SYS.DBA_SUPPLEMENTAL_LOGGING TO c##datastream CONTAINER=ALL;

-- 2. Configure application database user inside Pluggable Database
ALTER SESSION SET CONTAINER = ORCLPDB1;

DECLARE
  u_exists EXCEPTION;
  PRAGMA EXCEPTION_INIT(u_exists, -1920);
BEGIN
  EXECUTE IMMEDIATE 'CREATE USER RB_INTEL_LEDGER_19C IDENTIFIED BY "${DB_PASSWORD}"';
EXCEPTION
  WHEN u_exists THEN
    EXECUTE IMMEDIATE 'ALTER USER RB_INTEL_LEDGER_19C IDENTIFIED BY "${DB_PASSWORD}"';
END;
/

GRANT CONNECT, RESOURCE, CREATE TABLE TO RB_INTEL_LEDGER_19C;
GRANT UNLIMITED TABLESPACE TO RB_INTEL_LEDGER_19C;

@/tmp/app_setup.sql
EXIT;
EOF

echo "Oracle database seeding completed successfully!"
