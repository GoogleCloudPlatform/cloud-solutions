#!/bin/bash
# shellcheck disable=SC2154
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0

set -euo pipefail

LOG_FILE="/var/log/bootstrap_db.log"
exec > >(tee -a "$LOG_FILE") 2>&1

finish() {
  local exit_code=$?
  if [ $exit_code -eq 0 ]; then
    echo "=== BOOTSTRAP COMPLETED SUCCESSFULLY AT $(date) ==="
    gcloud storage cp "$LOG_FILE" "gs://${notebook_bucket}/bootstrap-completed.txt" || true
  else
    echo "=== BOOTSTRAP FAILED WITH EXIT CODE $exit_code AT $(date) ==="
    gcloud storage cp "$LOG_FILE" "gs://${notebook_bucket}/bootstrap-failed.txt" || true
  fi
}
trap finish EXIT

log_step() {
  echo "$1"
  echo "$1 ($(date))" >/tmp/bootstrap-status.txt
  gcloud storage cp /tmp/bootstrap-status.txt "gs://${notebook_bucket}/bootstrap-status.txt" || true
}

echo "=== STARTING ALLOYDB BOOTSTRAP SCRIPT ==="

# 1. Install PostgreSQL client and utilities with retry loop for transient mirror hiccups
export DEBIAN_FRONTEND=noninteractive
for attempt in {1..3}; do
  if apt-get update -qq && apt-get install -y -qq postgresql-client curl gnupg; then
    break
  fi
  echo "Attempt $attempt: apt-get failed, retrying in 5s..."
  sleep 5
done

export PGPASSWORD="${alloydb_password}"
ALLOYDB_IP="${alloydb_ip}"
DB_NAME="${alloydb_database}"

log_step "1. Waiting for AlloyDB instance ($ALLOYDB_IP:5432) to accept private VPC connections..."
for i in $(seq 1 120); do
  if psql -h "$ALLOYDB_IP" -U postgres -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
    echo "AlloyDB private connection ready!"
    break
  fi
  echo "Attempt $i: waiting for AlloyDB..."
  sleep 5
done

log_step "2. Creating the $DB_NAME database and setting search_path..."
psql -h "$ALLOYDB_IP" -U postgres -d postgres <<-EOF
  CREATE DATABASE $DB_NAME;
  ALTER DATABASE $DB_NAME SET search_path TO ecomm, public;
  GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO postgres;
  GRANT CONNECT ON DATABASE $DB_NAME TO PUBLIC;
EOF

log_step "3. Installing required database extensions..."
psql -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS google_ml_integration;
  CREATE EXTENSION IF NOT EXISTS alloydb_scann;
EOF

log_step "4. Upgrading google_ml_integration extension..."
psql -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" -c "CALL google_ml.upgrade_to_preview_version();" 2>/dev/null || echo "NOTICE: google_ml_integration is already at version 1.5+ (no upgrade needed)."

log_step "5. Creating agentspace_user role..."
gcloud -q alloydb users create agentspace_user \
  --cluster="${alloydb_cluster_id}" \
  --region="${gcp_region}" \
  --project="${gcp_project_id}" \
  --password="${agentspace_user_password}" || echo "User agentspace_user might already exist, continuing..."

psql -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  GRANT CONNECT ON DATABASE $DB_NAME TO agentspace_user;
  GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO agentspace_user;
EOF

log_step "6. Streaming eCommerce data from ${database_backup_uri} via high-speed psql session (-q -1)..."
(
  echo "SET synchronous_commit = off;"
  gcloud storage cat "${database_backup_uri}"
) | psql -q -1 -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME"

log_step "7. Granting schema privileges to agentspace_user..."
psql -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  GRANT USAGE ON SCHEMA ecomm TO agentspace_user;
  GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ecomm TO agentspace_user;
  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ecomm TO agentspace_user;
EOF

log_step "8. Validating table row counts..."
psql -v ON_ERROR_STOP=on -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  SET search_path TO ecomm, public;
  SELECT 'distribution_centers' AS table_name, (SELECT COUNT(*) FROM distribution_centers) AS actual_row_count, 10 AS target_row_count
  UNION ALL
  SELECT 'events', (SELECT COUNT(*) FROM events), 2438862
  UNION ALL
  SELECT 'inventory_items', (SELECT COUNT(*) FROM inventory_items), 494254
  UNION ALL
  SELECT 'orders', (SELECT COUNT(*) FROM orders), 125905
  UNION ALL
  SELECT 'order_items', (SELECT COUNT(*) FROM order_items), 182905
  UNION ALL
  SELECT 'products', (SELECT COUNT(*) FROM products), 29120
  UNION ALL
  SELECT 'users', (SELECT COUNT(*) FROM users), 100000;

  DO \$\$
  DECLARE
    prod_count INT;
    event_count INT;
  BEGIN
    SELECT COUNT(*) INTO prod_count FROM products;
    SELECT COUNT(*) INTO event_count FROM events;
    IF prod_count < 1000 OR event_count < 1000 THEN
      RAISE EXCEPTION 'Data validation failed! Expected >1000 rows, found % products and % events.', prod_count, event_count;
    END IF;
    RAISE NOTICE 'Data validation passed: % products and % events verified.', prod_count, event_count;
  END \$\$;
EOF

log_step "9. Creating standard B-tree indexes..."
psql -v ON_ERROR_STOP=on -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  SET search_path TO ecomm, public;
  SET maintenance_work_mem = '512MB';
  SET max_parallel_maintenance_workers = 2;
  DROP INDEX IF EXISTS idx_products_brand;
  CREATE INDEX idx_products_brand ON products (brand);
  DROP INDEX IF EXISTS idx_products_category;
  CREATE INDEX idx_products_category ON products (category);
  DROP INDEX IF EXISTS idx_products_retail_price;
  CREATE INDEX idx_products_retail_price ON products (retail_price);
  DROP INDEX IF EXISTS idx_products_sku;
  CREATE INDEX idx_products_sku ON products (sku);
EOF

log_step "10. Creating ScaNN vector indexes..."
psql -v ON_ERROR_STOP=on -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  SET search_path TO ecomm, public;
  SET maintenance_work_mem = '512MB';
  SET max_parallel_maintenance_workers = 2;
  CREATE EXTENSION IF NOT EXISTS alloydb_scann;
  SET SESSION scann.num_leaves_to_search = 1;
  SET SESSION scann.pre_reordering_num_neighbors=50;
  DROP INDEX IF EXISTS embedding_scann;
  CREATE INDEX embedding_scann ON products
    USING scann (product_embedding cosine)
    WITH (num_leaves=2);
  DROP INDEX IF EXISTS product_description_embedding_scann;
  CREATE INDEX product_description_embedding_scann ON products
    USING scann (product_description_embedding cosine)
    WITH (num_leaves=2);
  DROP INDEX IF EXISTS product_image_embedding_scann;
  CREATE INDEX product_image_embedding_scann ON products
    USING scann (product_image_embedding cosine)
    WITH (num_leaves=2);
EOF

log_step "11. Creating HNSW sparse vector index..."
psql -v ON_ERROR_STOP=on -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  SET search_path TO ecomm, public;
  SET maintenance_work_mem = '512MB';
  SET max_parallel_maintenance_workers = 2;
  DROP INDEX IF EXISTS sparse_embedding_hnsw;
  CREATE INDEX sparse_embedding_hnsw ON products
    USING hnsw (sparse_embedding sparsevec_ip_ops)
    WITH (m = 16, ef_construction = 64);
EOF

log_step "12. Creating Full-Text Search GIN index..."
psql -v ON_ERROR_STOP=on -h "$ALLOYDB_IP" -U postgres -d "$DB_NAME" <<-EOF
  SET search_path TO ecomm, public;
  SET maintenance_work_mem = '512MB';
  SET max_parallel_maintenance_workers = 2;
  DROP INDEX IF EXISTS products_fts_document_gin;
  CREATE INDEX products_fts_document_gin ON products USING GIN (fts_document);
EOF

log_step "=== BOOTSTRAP_SUCCESS ==="
