#!/bin/bash
# shellcheck disable=SC2154,SC2086
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset
set -o pipefail

# =============================================================================
# CONFIGURATION - Update these values
# =============================================================================
VM_NAME="hero-demo-app"
ZONE="us-east1-b"
CLOUD_SQL_INSTANCE="postgres-instance"
NETWORK="default"

# Database credentials
DB_NAME="appdb"
DB_USER="appuser"
DB_PASSWORD="SecureAppPass123!"
DB_PORT="5432"

# =============================================================================
# GET CLOUD SQL PRIVATE IP
# =============================================================================
echo "Getting Cloud SQL private IP..."
CLOUD_SQL_IP=$(gcloud sql instances describe $CLOUD_SQL_INSTANCE \
  --format=json | jq -r '.ipAddresses[] | select(.type=="PRIVATE") | .ipAddress')

if [ -z "$CLOUD_SQL_IP" ]; then
  echo "Error: Could not get Cloud SQL private IP."
  echo "Make sure private IP is enabled on the Cloud SQL instance."
  exit 1
fi

echo "Cloud SQL Private IP: $CLOUD_SQL_IP"

# =============================================================================
# CREATE FIREWALL RULES
# =============================================================================
echo "Creating firewall rules..."

# SSH firewall rule
if ! gcloud compute firewall-rules describe allow-ssh &>/dev/null; then
  gcloud compute firewall-rules create allow-ssh \
    --network=$NETWORK \
    --allow=tcp:22 \
    --source-ranges=0.0.0.0/0 \
    --description="Allow SSH access"
  echo "Created allow-ssh firewall rule"
else
  echo "allow-ssh firewall rule already exists"
fi

# Health check firewall rule
if ! gcloud compute firewall-rules describe allow-flask-health-check &>/dev/null; then
  gcloud compute firewall-rules create allow-flask-health-check \
    --network=$NETWORK \
    --allow=tcp:5000 \
    --source-ranges=130.211.0.0/22,35.191.0.0/16 \
    --description="Allow GCP health checks to Flask app"
  echo "Created allow-flask-health-check firewall rule"
else
  echo "allow-flask-health-check firewall rule already exists"
fi

# =============================================================================
# ADD CLOUD SQL INSTANCE USER
# =============================================================================
echo "Adding user to Cloud SQL instance"
gcloud sql users create $DB_USER \
  --instance=$CLOUD_SQL_INSTANCE \
  --password=$DB_PASSWORD
# =============================================================================
# UPDATE VM DATABASE CONNECTION
# =============================================================================
echo "Updating VM database connection and granting permissions..."

gcloud compute ssh $VM_NAME --zone=$ZONE --command="
# 1. Install PostgreSQL Client (Required to run the GRANT command)
if ! command -v psql &> /dev/null; then
    echo 'Installing postgresql-client...'
    sudo apt-get update -qq && sudo apt-get install -y -qq postgresql-client
fi

# 2. Grant Permissions
# We connect to $DB_NAME (appdb) as 'postgres' using the shared password
echo 'Granting table permissions...'
export PGPASSWORD='$DB_PASSWORD'

# Wait a moment for network/DB readiness
sleep 2

psql \"host=$CLOUD_SQL_IP user=postgres dbname=$DB_NAME sslmode=disable\" \
  -c \"GRANT ALL PRIVILEGES ON TABLE users TO \\\"$DB_USER\\\";\"

# 3. Update .env file
echo 'Updating .env file...'
sudo tee /opt/flask-app/.env > /dev/null <<EOF
DB_HOST=$CLOUD_SQL_IP
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
EOF

# 4. Restart Flask App
echo 'Restarting Flask service...'
sudo systemctl daemon-reload
sudo systemctl restart flask-app
sleep 3
curl -s http://localhost:5000/health
"

# =============================================================================
# CREATE INSTANCE GROUP
# =============================================================================
echo "Creating instance group..."

if ! gcloud compute instance-groups unmanaged describe flask-ig \
  --zone=$ZONE &>/dev/null; then
  gcloud compute instance-groups unmanaged create flask-ig \
    --zone=$ZONE
  echo "Created flask-ig instance group"
else
  echo "flask-ig instance group already exists"
fi

# Add VM to instance group
gcloud compute instance-groups unmanaged add-instances flask-ig \
  --zone=$ZONE \
  --instances=$VM_NAME 2>/dev/null || echo "VM already in instance group"

# Set named ports
gcloud compute instance-groups unmanaged set-named-ports flask-ig \
  --zone=$ZONE \
  --named-ports=http:5000

# =============================================================================
# CREATE HEALTH CHECK
# =============================================================================
echo "Creating health check..."

if ! gcloud compute health-checks describe flask-health-check &>/dev/null; then
  gcloud compute health-checks create http flask-health-check \
    --port=5000 \
    --request-path=/health
  echo "Created flask-health-check"
else
  echo "flask-health-check already exists"
fi

# =============================================================================
# CREATE BACKEND SERVICE
# =============================================================================
echo "Creating backend service..."

if ! gcloud compute backend-services describe flask-backend \
  --global &>/dev/null; then
  gcloud compute backend-services create flask-backend \
    --protocol=HTTP \
    --port-name=http \
    --health-checks=flask-health-check \
    --global
  echo "Created flask-backend"
else
  echo "flask-backend already exists"
fi

# Add backend
gcloud compute backend-services add-backend flask-backend \
  --instance-group=flask-ig \
  --instance-group-zone=$ZONE \
  --global 2>/dev/null || echo "Backend already added"

# =============================================================================
# CREATE URL MAP AND PROXY
# =============================================================================
echo "Creating URL map and proxy..."

if ! gcloud compute url-maps describe flask-url-map &>/dev/null; then
  gcloud compute url-maps create flask-url-map \
    --default-service=flask-backend
  echo "Created flask-url-map"
else
  echo "flask-url-map already exists"
fi

if ! gcloud compute target-http-proxies describe flask-http-proxy &>/dev/null; then
  gcloud compute target-http-proxies create flask-http-proxy \
    --url-map=flask-url-map
  echo "Created flask-http-proxy"
else
  echo "flask-http-proxy already exists"
fi

# =============================================================================
# CREATE FORWARDING RULE
# =============================================================================
echo "Creating forwarding rule..."

if ! gcloud compute forwarding-rules describe flask-http-rule \
  --global &>/dev/null; then
  gcloud compute forwarding-rules create flask-http-rule \
    --global \
    --target-http-proxy=flask-http-proxy \
    --ports=80
  echo "Created flask-http-rule"
else
  echo "flask-http-rule already exists"
fi

# =============================================================================
# GET LOAD BALANCER IP AND VERIFY
# =============================================================================
echo ""
echo "============================================================"
echo "DEPLOYMENT COMPLETE"
echo "============================================================"

LB_IP=$(gcloud compute forwarding-rules describe flask-http-rule \
  --global --format='value(IPAddress)')

echo ""
echo "Load Balancer IP: $LB_IP"
echo "Cloud SQL IP: $CLOUD_SQL_IP"
echo ""
echo "Wait 2-3 minutes for health checks to pass, then test:"
echo ""
echo "  curl http://$LB_IP/health"
echo "  curl http://$LB_IP/api/users"
echo ""
echo "============================================================"
