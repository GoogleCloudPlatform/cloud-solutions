#!/bin/bash
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
# These variables map to environment variables or must be injected before running.
# The syntax :? ensures the script exits immediately if the variable is not set.

db_host="${DB_HOST:?Error: Environment variable DB_HOST is required}"
db_port="${DB_PORT:-5432}" # Default to 5432 if not set
db_name="${DB_NAME:?Error: Environment variable DB_NAME is required}"

# Master Credentials (AWS RDS Source or similar)
db_master_user="${DB_MASTER_USER:?Error: Environment variable DB_MASTER_USER is required}"
db_master_password="${DB_MASTER_PASSWORD:?Error: Environment variable DB_MASTER_PASSWORD is required}"

# Application User Credentials (To be created)
db_user="${DB_USER:?Error: Environment variable DB_USER is required}"
db_password="${DB_PASSWORD:?Error: Environment variable DB_PASSWORD is required}"

# DMS User Credentials (To be created for migration)
dms_user="${DMS_USER:?Error: Environment variable DMS_USER is required}"
dms_password="${DMS_PASSWORD:?Error: Environment variable DMS_PASSWORD is required}"

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
mkdir -p /opt/flask-app
cd /opt/flask-app

cat >/opt/flask-app/app.py <<'APPEOF'
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import socket

app = Flask(__name__)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'appdb'),
    'user': os.environ.get('DB_USER', 'appuser'),
    'password': os.environ.get('DB_PASSWORD', '')
}

def get_db():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

@app.route('/health')
def health():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.close()
        conn.close()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'hostname': socket.gethostname(),
            'db_host': DB_CONFIG['host']
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'hostname': socket.gethostname()
        }), 500

@app.route('/')
def index():
    return jsonify({
        'message': 'Application API',
        'version': '1.0.0',
        'hostname': socket.gethostname(),
        'endpoints': [
            {'method': 'GET', 'path': '/health', 'description': 'Health check'},
            {'method': 'GET', 'path': '/api/users', 'description': 'List all users'},
            {'method': 'GET', 'path': '/api/users/<id>', 'description': 'Get user by ID'},
            {'method': 'POST', 'path': '/api/users', 'description': 'Create new user'},
            {'method': 'DELETE', 'path': '/api/users/<id>', 'description': 'Delete user'}
        ]
    })

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users ORDER BY id')
        users = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({'count': len(users), 'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return jsonify(user)
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'email' not in data:
            return jsonify({'error': 'name and email are required'}), 400
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO users (name, email, department) VALUES (%s, %s, %s) RETURNING *',
            (data['name'], data['email'], data.get('department', 'General'))
        )
        user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(user), 201
    except psycopg2.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE id = %s RETURNING id', (user_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if deleted:
            return jsonify({'message': f'User {user_id} deleted'})
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
APPEOF

python3 -m venv /opt/flask-app/venv
/opt/flask-app/venv/bin/pip install flask psycopg2-binary gunicorn

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
