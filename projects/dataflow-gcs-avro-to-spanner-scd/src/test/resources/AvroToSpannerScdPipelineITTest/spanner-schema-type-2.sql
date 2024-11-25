-- Copyright 2024 Google LLC
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

CREATE TABLE employees (
  id INT64 NOT NULL,
  first_name STRING(50) NOT NULL,
  last_name STRING(50) NOT NULL,
  department STRING(50) NOT NULL,
  salary FLOAT64 NOT NULL,
  hire_date DATE NOT NULL,
  start_date TIMESTAMP NOT NULL,
  end_date TIMESTAMP,
) PRIMARY KEY (id, end_date);
