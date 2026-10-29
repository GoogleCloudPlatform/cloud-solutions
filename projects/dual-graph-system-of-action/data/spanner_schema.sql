-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

CREATE TABLE policies (
  policy_id STRING(64) NOT NULL,
  name STRING(256) NOT NULL,
  source_document_uri STRING(512),
  policy_version STRING(32),
  status STRING(32) NOT NULL,
  valid_from TIMESTAMP NOT NULL,
  valid_to TIMESTAMP
) PRIMARY KEY (policy_id);

CREATE TABLE policy_conditions (
  condition_id STRING(64) NOT NULL,
  policy_id STRING(64) NOT NULL,
  applicable_tier STRING(32) NOT NULL,
  max_refunds_100d INT64 NOT NULL,
  return_window_days INT64 NOT NULL,
  threshold_expression STRING(256) NOT NULL,
  CONSTRAINT fk_condition_policy FOREIGN KEY (policy_id) REFERENCES policies (policy_id)
) PRIMARY KEY (condition_id);

CREATE TABLE policy_restrictions (
  restriction_id STRING(64) NOT NULL,
  policy_id STRING(64) NOT NULL,
  action_code STRING(64) NOT NULL,
  description STRING(512),
  CONSTRAINT fk_restriction_policy FOREIGN KEY (policy_id) REFERENCES policies (policy_id)
) PRIMARY KEY (restriction_id);

CREATE TABLE distribution_centers (
  id INT64 NOT NULL,
  name STRING(256),
  latitude FLOAT64,
  longitude FLOAT64
) PRIMARY KEY (id);

CREATE TABLE users (
  id INT64 NOT NULL,
  first_name STRING(128),
  last_name STRING(128),
  email STRING(256),
  customer_tier STRING(32) NOT NULL,
  age INT64,
  gender STRING(32),
  state STRING(128),
  street_address STRING(256),
  postal_code STRING(64),
  city STRING(128),
  country STRING(128),
  latitude FLOAT64,
  longitude FLOAT64,
  traffic_source STRING(128),
  created_at TIMESTAMP
) PRIMARY KEY (id);

CREATE TABLE products (
  id INT64 NOT NULL,
  cost FLOAT64,
  category STRING(128),
  name STRING(256),
  brand STRING(128),
  retail_price FLOAT64,
  department STRING(128),
  sku STRING(128),
  distribution_center_id INT64 NOT NULL,
  policy_id STRING(64) NOT NULL,
  CONSTRAINT fk_product_dc FOREIGN KEY (distribution_center_id) REFERENCES distribution_centers (id),
  CONSTRAINT fk_product_policy FOREIGN KEY (policy_id) REFERENCES policies (policy_id)
) PRIMARY KEY (id);

CREATE TABLE inventory_items (
  id INT64 NOT NULL,
  product_id INT64 NOT NULL,
  created_at TIMESTAMP,
  sold_at TIMESTAMP,
  cost FLOAT64,
  product_category STRING(128),
  product_name STRING(256),
  product_brand STRING(128),
  product_retail_price FLOAT64,
  product_department STRING(128),
  product_sku STRING(128),
  product_distribution_center_id INT64,
  CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_inventory_dc FOREIGN KEY (product_distribution_center_id) REFERENCES distribution_centers (id)
) PRIMARY KEY (id);

CREATE TABLE orders (
  order_id INT64 NOT NULL,
  user_id INT64 NOT NULL,
  status STRING(64) NOT NULL,
  gender STRING(32),
  created_at TIMESTAMP NOT NULL,
  returned_at TIMESTAMP,
  shipped_at TIMESTAMP,
  delivered_at TIMESTAMP,
  num_of_item INT64,
  CONSTRAINT fk_order_user FOREIGN KEY (user_id) REFERENCES users (id)
) PRIMARY KEY (order_id);

CREATE TABLE order_items (
  id INT64 NOT NULL,
  order_id INT64 NOT NULL,
  user_id INT64 NOT NULL,
  product_id INT64 NOT NULL,
  inventory_item_id INT64 NOT NULL,
  status STRING(64) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  shipped_at TIMESTAMP,
  delivered_at TIMESTAMP,
  returned_at TIMESTAMP,
  sale_price FLOAT64 NOT NULL,
  refund_trace_id STRING(128),
  CONSTRAINT fk_order_item_order FOREIGN KEY (order_id) REFERENCES orders (order_id),
  CONSTRAINT fk_order_item_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_order_item_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_order_item_inventory FOREIGN KEY (inventory_item_id) REFERENCES inventory_items (id)
) PRIMARY KEY (id);

CREATE INDEX idx_orders_user_created
  ON orders (user_id, created_at DESC)
  STORING (status, returned_at, delivered_at);

CREATE INDEX idx_order_items_order_status
  ON order_items (order_id, status)
  STORING (inventory_item_id, sale_price, returned_at, refund_trace_id);

CREATE PROPERTY GRAPH OperationalContextGraph
  NODE TABLES (
    users,
    products,
    orders,
    distribution_centers,
    inventory_items,
    policies,
    policy_conditions,
    policy_restrictions
  )
  EDGE TABLES (
    orders AS places
      SOURCE KEY (user_id) REFERENCES users (id)
      DESTINATION KEY (order_id) REFERENCES orders (order_id)
      LABEL places,
    order_items AS contains_item
      SOURCE KEY (order_id) REFERENCES orders (order_id)
      DESTINATION KEY (inventory_item_id) REFERENCES inventory_items (id)
      LABEL contains_item,
    inventory_items AS is_product
      SOURCE KEY (id) REFERENCES inventory_items (id)
      DESTINATION KEY (product_id) REFERENCES products (id)
      LABEL is_product,
    products AS supplied_by
      SOURCE KEY (id) REFERENCES products (id)
      DESTINATION KEY (distribution_center_id) REFERENCES distribution_centers (id)
      LABEL supplied_by,
    products AS governed_by
      SOURCE KEY (id) REFERENCES products (id)
      DESTINATION KEY (policy_id) REFERENCES policies (policy_id)
      LABEL governed_by,
    policy_conditions AS requires_condition
      SOURCE KEY (policy_id) REFERENCES policies (policy_id)
      DESTINATION KEY (condition_id) REFERENCES policy_conditions (condition_id)
      LABEL requires_condition,
    policy_restrictions AS enforces_restriction
      SOURCE KEY (policy_id) REFERENCES policies (policy_id)
      DESTINATION KEY (restriction_id) REFERENCES policy_restrictions (restriction_id)
      LABEL enforces_restriction
  );
