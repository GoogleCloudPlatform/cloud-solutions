---
name: spanner-provisioning
description: >
  Guidelines and rules for provisioning Google Cloud Spanner instances, including selecting
  the correct edition (Enterprise vs Standard) and compute capacity based on schema features
  (e.g., graphs and vector search) and environment purpose.
---

# Spanner Instance Provisioning Guidelines

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

Use this skill when provisioning, configuring, or updating a Cloud Spanner
instance in this repository.

## 1. Edition Selection Rules

Spanner features are associated with specific database editions. To optimize
costs while ensuring functionality:

- **ENTERPRISE Edition**: Must be selected if the database schema utilizes
  features such as:
    - **Spanner Graph**: Identified by the presence of `CREATE PROPERTY GRAPH`
      in the DDL.
    - **Vector Search Index**: Identified by the presence of
      `CREATE VECTOR INDEX` in the DDL.
- **STANDARD Edition**: Should be selected for basic relational workloads that
  do not use graph traversal or vector search.

## 2. Compute Capacity Rules

Compute capacity (processing units) must be chosen based on the environment's
purpose:

- **Development & Testing (`dev` / `test`)**:
    - Enforce the minimum compute capacity of **100 processing units** to
      minimize cloud expenditures.
- **Production (`prod`)**:
    - Minimum compute capacity should start at **1000 processing units**
      (equivalent to 1 node) or higher as required by workload demands, unless
      autoscaling is configured.

## 3. Idempotency and Schema Application

When applying DDL schemas to an existing Spanner database:

- **Avoid Duplication Errors**: Standard Spanner DDL statements (like
  `CREATE TABLE`, `CREATE PROPERTY GRAPH`, or `CREATE VECTOR INDEX`) will return
  errors if the object already exists.
- **Verification Check**: Before applying the full DDL schema, verify if key
  objects (e.g., node tables) already exist in the database.
    - You can query `INFORMATION_SCHEMA.TABLES` (e.g., checking if the primary
      table name is present) to determine if the schema has been initialized.
    - If the database schema is already initialized, skip executing duplicate
      creation DDL statements.
- **Schema Updates**: For incremental updates, use compatible statements (such
  as `ALTER TABLE`) rather than running the full creation script.
- **Recreation**: If a complete schema reset is required, drop and recreate the
  database before applying the full schema.
