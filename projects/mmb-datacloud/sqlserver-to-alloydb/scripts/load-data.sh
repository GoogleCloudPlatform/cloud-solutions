#!/bin/bash
# Copyright 2026 Google LLC
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

# Redirect stdout and stderr to a log file
exec > >(tee -i /var/log/startup-script.log) 2>&1

echo "Starting startup script..."

# Update package lists
apt-get update -y

# Install gnupg, curl, google-cloud-cli, and Python libraries via apt
apt-get install -y \
  apt-transport-https \
  curl \
  gnupg \
  google-cloud-cli \
  python3 \
  python3-pandas \
  python3-pyodbc \
  python3-sqlalchemy \
  unixodbc-dev

# Add Microsoft package repository for ODBC Driver 18
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor --yes -o /usr/share/keyrings/microsoft-prod.gpg
echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" >/etc/apt/sources.list.d/mssql-release.list

apt-get update -y

# Install Microsoft ODBC Driver 18 (accept EULA)
ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18
echo "export PATH=\"\$PATH:/opt/mssql-tools18/bin\"" >>/etc/profile.d/mssql.sh

# Export data from BigQuery public dataset to CSV files
echo "Exporting tables from BigQuery public dataset..."
TABLES=(
  "distribution_centers"
  "events"
  "inventory_items"
  "order_items"
  "orders"
  "products"
  "users"
)

for TABLE in "${TABLES[@]}"; do
  echo "Exporting ${TABLE} from BigQuery..."
  if [ "${TABLE}" = "events" ]; then
    QUERY="SELECT * FROM \`bigquery-public-data.thelook_ecommerce.${TABLE}\` LIMIT 100000"
  else
    QUERY="SELECT * FROM \`bigquery-public-data.thelook_ecommerce.${TABLE}\`"
  fi
  bq --quiet query --use_legacy_sql=false --format=csv --max_rows=1000000 "${QUERY}" >"/tmp/${TABLE}.csv"
  if [ ! -s "/tmp/${TABLE}.csv" ]; then
    echo "Warning: Exported CSV file /tmp/${TABLE}.csv is empty or missing."
  fi
done

# Write the python script to load data into SQL Server
cat <<'EOF' >/opt/load_data.py
import os
import socket
import time
import urllib.parse
import urllib.request
import pandas as pd
from sqlalchemy import create_engine, exc, text
from sqlalchemy.types import DateTime, Float, Integer, String

def get_metadata(key):
    req = urllib.request.Request(
        f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{key}",
        headers={"Metadata-Flavor": "Google"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching metadata {key}: {e}")
        return None

sql_server_ip = get_metadata("SQL_SERVER_IP")
sql_server_password = get_metadata("SQL_SERVER_PASSWORD")

if not sql_server_ip or not sql_server_password:
    print("Missing SQL Server IP or Password in metadata.")
    exit(1)

# Wait for SQL Server to be ready
print(f"Waiting for SQL Server at {sql_server_ip}:1433 to be ready...")
while True:
    try:
        with socket.create_connection((sql_server_ip, 1433), timeout=5):
            print("SQL Server is up!")
            break
    except OSError:
        print("SQL Server not ready yet, sleeping 10s...")
        time.sleep(10)

# Connect to master database to create the database
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={sql_server_ip};"
    "DATABASE=master;"
    "UID=sqlserver;"
    f"PWD={sql_server_password};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# Create database
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    result = conn.execute(text("SELECT name FROM sys.databases WHERE name = 'thelook_ecommerce'"))
    if not result.fetchone():
        conn.execute(text("CREATE DATABASE thelook_ecommerce;"))
        print("Database thelook_ecommerce created.")
    else:
        print("Database thelook_ecommerce already exists.")

# Reconnect to thelook_ecommerce database
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={sql_server_ip};"
    "DATABASE=thelook_ecommerce;"
    "UID=sqlserver;"
    f"PWD={sql_server_password};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)

# Define data types for schema mapping
dtypes_map = {
    'distribution_centers': {
        'id': Integer(),
        'name': String(255),
        'latitude': Float(),
        'longitude': Float()
    },
    'products': {
        'id': Integer(),
        'cost': Float(),
        'category': String(255),
        'name': String(255),
        'brand': String(255),
        'retail_price': Float(),
        'department': String(255),
        'sku': String(255),
        'distribution_center_id': Integer()
    },
    'users': {
        'id': Integer(),
        'first_name': String(255),
        'last_name': String(255),
        'email': String(255),
        'age': Integer(),
        'gender': String(50),
        'state': String(255),
        'street_address': String(500),
        'postal_code': String(50),
        'city': String(255),
        'country': String(255),
        'latitude': Float(),
        'longitude': Float(),
        'traffic_source': String(255),
        'created_at': DateTime()
    },
    'orders': {
        'order_id': Integer(),
        'user_id': Integer(),
        'status': String(50),
        'gender': String(50),
        'created_at': DateTime(),
        'returned_at': DateTime(),
        'shipped_at': DateTime(),
        'delivered_at': DateTime(),
        'num_of_item': Integer()
    },
    'order_items': {
        'id': Integer(),
        'order_id': Integer(),
        'user_id': Integer(),
        'product_id': Integer(),
        'inventory_item_id': Integer(),
        'status': String(50),
        'created_at': DateTime(),
        'shipped_at': DateTime(),
        'delivered_at': DateTime(),
        'returned_at': DateTime(),
        'sale_price': Float()
    },
    'inventory_items': {
        'id': Integer(),
        'product_id': Integer(),
        'created_at': DateTime(),
        'sold_at': DateTime(),
        'cost': Float(),
        'product_category': String(255),
        'product_name': String(255),
        'product_brand': String(255),
        'product_retail_price': Float(),
        'product_department': String(255),
        'product_sku': String(255),
        'product_distribution_center_id': Integer()
    },
    'events': {
        'id': Integer(),
        'user_id': Integer(),
        'sequence_number': Integer(),
        'session_id': String(255),
        'created_at': DateTime(),
        'ip_address': String(50),
        'city': String(255),
        'state': String(255),
        'postal_code': String(50),
        'browser': String(50),
        'traffic_source': String(255),
        'uri': String(500),
        'event_type': String(50)
    }
}

for table, dtypes in dtypes_map.items():
    print(f"Loading table {table} into SQL Server...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.fetchone()[0]
            if count > 0:
                print(f"Table {table} already exists and has {count} rows. Skipping.")
                continue
    except (exc.DBAPIError, exc.ProgrammingError) as e:
        print(f"Notice: Querying table {table} produced: {e}")

    csv_path = f"/tmp/{table}.csv"
    if not os.path.exists(csv_path):
        print(f"CSV file {csv_path} not found. Skipping.")
        continue

    try:
        df = pd.read_csv(csv_path)
        # Parse datetime columns
        for col, col_type in dtypes.items():
            if isinstance(col_type, DateTime) and col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        print(f"Read {len(df)} rows from {csv_path}. Writing to SQL Server...")
        df.to_sql(
            table,
            engine,
            if_exists='replace',
            index=False,
            dtype=dtypes,
            chunksize=5000
        )
        print(f"Table {table} successfully loaded.")
    except Exception as e:
        print(f"Error loading table {table}: {e}")

print("Data loading process complete.")
EOF

# Run the python script
echo "Running the data loader script..."
python3 /opt/load_data.py

echo "Startup script finished."
