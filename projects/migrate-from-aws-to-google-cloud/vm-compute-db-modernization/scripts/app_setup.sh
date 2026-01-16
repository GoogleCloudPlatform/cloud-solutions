#!/bin/bash
# shellcheck disable=SC2154
# Variables are injected by Terraform templatefile function
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset
set -o pipefail

# -----------------------------------------------------------------------------
# Configuration & Input Validation
# -----------------------------------------------------------------------------

echo "Starting app server setup..."

# 1. Install Dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv postgresql-client

# 2. Wait for RDS Availability
echo "Waiting for RDS to be available..."
until PGPASSWORD="${db_master_password}" psql -h "${db_host}" -U "${db_master_user}" -d "${db_name}" -c "SELECT 1" >/dev/null 2>&1; do
  echo "RDS not ready, waiting..."
  sleep 10
done
echo "RDS is available"

# 3. Database Setup (Users, Schema, Data, Permissions)
echo "Setting up database users, grants, schema, and data..."
PGPASSWORD="${db_master_password}" psql -h "${db_host}" -U "${db_master_user}" -d "${db_name}" <<EOSQL

-- ====================================================================
-- A. USER CREATION
-- ====================================================================

-- Create App User
CREATE USER ${db_user} WITH PASSWORD '${db_password}';
GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_user};

-- Create DMS User
CREATE USER ${dms_user} WITH PASSWORD '${dms_password}' LOGIN;
GRANT rds_replication TO ${dms_user};

-- ====================================================================
-- B. SCHEMA AND DATA (The Application)
-- ====================================================================

-- Install pglogical (Idempotent)
CREATE EXTENSION IF NOT EXISTS pglogical;

-- Create Application Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert Sample Data
INSERT INTO users (name, email, department) VALUES
('Alice Johnson', 'alice@example.com', 'Engineering'),
('Bob Smith', 'bob@example.com', 'Marketing'),
('Carol White', 'carol@example.com', 'Engineering'),
('David Brown', 'david@example.com', 'Sales'),
('Emma Davis', 'emma@example.com', 'HR'),
('Frank Miller', 'frank@example.com', 'Engineering'),
('Grace Lee', 'grace@example.com', 'Marketing'),
('Henry Wilson', 'henry@example.com', 'Sales'),
('Ivy Chen', 'ivy@example.com', 'Engineering'),
('Jack Taylor', 'jack@example.com', 'HR')
ON CONFLICT (email) DO NOTHING;

-- ====================================================================
-- C. PERMISSIONS
-- ====================================================================

-- 1. App User Permissions (Standard)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${db_user};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${db_user};
GRANT USAGE ON SCHEMA public TO ${db_user};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${db_user};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${db_user};

-- 2. DMS User - pglogical Specifics (CRITICAL FOR MIGRATION)
-- Fixes: "replication user doesn't have USAGE privilege on schema pglogical"
GRANT USAGE ON SCHEMA pglogical TO ${dms_user};
GRANT SELECT ON ALL TABLES IN SCHEMA pglogical TO ${dms_user};
GRANT USAGE ON SCHEMA pglogical TO PUBLIC;

-- 3. DMS User - Dynamic Loop for ALL Schemas
-- This ensures DMS can read any schema you create (public, sales, etc.)
DO \$migration\$
DECLARE
    sch text;
BEGIN
    FOR sch IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname NOT LIKE 'pg_%'
          AND nspname <> 'information_schema'
    LOOP
        -- Grant USAGE on the schema
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO ${dms_user}', sch);

        -- Grant SELECT on tables and sequences
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO ${dms_user}', sch);
        EXECUTE format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA %I TO ${dms_user}', sch);

        -- Ensure future tables are readable
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO ${dms_user}', sch);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON SEQUENCES TO ${dms_user}', sch);
    END LOOP;
END
\$migration\$;

EOSQL
echo "Database setup complete"

# 4. Flask Application Setup
cd /opt/flask-app

python3 -m venv /opt/flask-app/venv
/opt/flask-app/venv/bin/pip install --index-url https://pypi.org/simple --require-hashes -r /opt/flask-app/requirements.txt

cat >/opt/flask-app/.env <<ENVEOF
DB_HOST=${db_host}
DB_PORT=${db_port}
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
ENVEOF

cat >/etc/systemd/system/flask-app.service <<'SVCEOF'
[Unit]
Description=Flask Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/flask-app
EnvironmentFile=/opt/flask-app/.env
ExecStart=/opt/flask-app/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable flask-app
systemctl start flask-app

echo "APP_READY" >/tmp/app_ready
echo "App server setup complete!"
