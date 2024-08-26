-- Copyright 2024 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     https://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

CREATE TABLE data_types_test (
    integer_field INT PRIMARY KEY,
    bigint_field BIGINT,
    boolean_field BOOLEAN,
    char_field CHAR(10),
    varchar_field VARCHAR(10),
    date_field DATE,
    double_field DOUBLE PRECISION,
    macaddr_field MACADDR,
    numeric_field NUMERIC(3),
    point_field point,
    real_field REAL,
    smallint_field SMALLINT,
    text_field TEXT,
    timestamp_field TIMESTAMP
);
