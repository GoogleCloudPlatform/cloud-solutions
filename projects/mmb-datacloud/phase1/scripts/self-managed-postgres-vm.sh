#!/bin/sh
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

#!/bin/bash

# Update package lists
apt-get update -qqy

# Regenerate locale, gnupg, google-cloud-sdk
apt-get install -qqy locales gnupg google-cloud-sdk
sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen
locale-gen
update-locale LANG=en_US.UTF-8

# Create the file repository configuration:
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# Import the repository signing key:
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Update the package lists:
apt-get update -qqy

# Install PostgreSQL 16
apt-get -y install postgresql-16 postgresql-16-pglogical

# Generate a random password
PGADMIN_PASSWORD=$(openssl rand -base64 12)

# Create a new user 'pgadmin' with the random password
sudo -u postgres psql -c "CREATE USER pgadmin WITH PASSWORD '$PGADMIN_PASSWORD';"
sudo -u postgres psql -c "ALTER USER pgadmin WITH SUPERUSER;"

# Allow connections from 10.0.0.0/8 subnet
sudo -u postgres psql -c "ALTER SYSTEM SET listen_addresses TO '*';"

# Log the password to a file
echo "pgadmin password: $PGADMIN_PASSWORD" >/var/log/pgadmin_password.log

# Download the CSV file
gcloud storage cp gs://cloud-samples-data/vertex-ai/managed_notebooks/fraud_detection/fraud_detection_data.csv /tmp/fraud_detection_data.csv

# Create a database named 'fraud_detection'
sudo -u postgres createdb fraud_detection

# Create the transactions table and import data
sudo -u postgres psql -d fraud_detection <<EOF
CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    step INTEGER,
    type VARCHAR(20),
    amount NUMERIC,
    nameOrig VARCHAR(255),
    oldbalanceOrg NUMERIC,
    newbalanceOrig NUMERIC,
    nameDest VARCHAR(255),
    oldbalanceDest NUMERIC,
    newbalanceDest NUMERIC,
    isFraud INTEGER,
    isFlaggedFraud INTEGER
);

\copy transactions(step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud) FROM '/tmp/fraud_detection_data.csv' DELIMITER ',' CSV HEADER;
EOF

# Update pg_hba.conf to allow connections from 10.0.0.0/8
echo "host    all             all             10.0.0.0/8              scram-sha-256" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf

# Add pglogical to the shared_preload_libraries list
sed -i "/#shared_preload_libraries = ''/a shared_preload_libraries = 'pglogical'" /etc/postgresql/16/main/postgresql.conf

# Change the wal_level from replica to logical
sed -i "/#wal_level = replica/a wal_level = 'logical'" /etc/postgresql/16/main/postgresql.conf

# Restart PostgreSQL to apply the changes
systemctl restart postgresql

# Install pglogical extension
sudo -u postgres psql -c "CREATE EXTENSION pglogical;"

# Create an pglogical extension for fraud_detection database
sudo -u postgres psql -d fraud_detection -c 'CREATE EXTENSION IF NOT EXISTS pglogical;'

# Add replication attributes to pgadmin user
sudo -u postgres psql -c 'ALTER USER pgadmin WITH REPLICATION;'
