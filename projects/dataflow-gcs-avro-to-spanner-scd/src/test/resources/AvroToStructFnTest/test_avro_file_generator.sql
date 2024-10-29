/*
 * Copyright (C) 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

CREATE OR REPLACE TABLE test_table (
  boolean_nullable BOOLEAN,
  boolean_required BOOLEAN NOT NULL,
  decimal_nullable NUMERIC,
  decimal_required NUMERIC NOT NULL,
  float_nullable FLOAT64,
  float_required FLOAT64 NOT NULL,
  integer_nullable INT64,
  integer_required INT64 NOT NULL,
  string_nullable STRING,
  string_required STRING NOT NULL,
  timestamp_nullable TIMESTAMP,
  timestamp_required TIMESTAMP NOT NULL
);

INSERT INTO test_table (
  boolean_nullable,
  boolean_required,
  decimal_nullable,
  decimal_required,
  float_nullable,
  float_required,
  integer_nullable,
  integer_required,
  string_nullable,
  string_required,
  timestamp_nullable,
  timestamp_required
)
VALUES
(
  TRUE,
  FALSE,
  14.15,
  16.17,
  1.23,
  4.56,
  12,
  13,
  'nullable string',
  'required string',
  '2024-01-01 00:00:00.000',
  '2024-01-01 00:00:00.000'
),
(
  NULL,
  TRUE,
  NULL,
  24.25,
  NULL,
  20.21,
  NULL,
  22,
  NULL,
  'another required string',
  NULL,
  '2024-12-31 23:59:59'
);
