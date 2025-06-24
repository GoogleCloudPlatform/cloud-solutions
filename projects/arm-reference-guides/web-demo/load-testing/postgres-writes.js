/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* global __ENV:readonly */

import sql from 'k6/x/sql';
import driver from 'k6/x/sql/driver/postgres';

const DB_USER = __ENV.DB_USER;
const DB_PASSWORD = __ENV.DB_PASSWORD;
const DB_HOST = __ENV.DB_HOST;
const DB_PORT = __ENV.DB_PORT;
const DB_NAME = __ENV.DB_NAME;

export const options = {
  stages: [
    // Stage 1: Ramp-up from 1 to 20 virtual users over 30 seconds.
    // This gradually increases the load on the system.
    {duration: '30s', target: 50},

    // Stage 2: Maintain 20 virtual users for 1 minute.
    // This is the main load testing phase.
    {duration: '1m', target: 50},

    // Stage 3: Ramp-down to 0 virtual users over 15 seconds.
    // This gradually decreases the load.
    {duration: '15s', target: 0},
  ],
};

const db = sql.open(driver, `postgres://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable`);

/**
 * Creates the table used for the test
 */
export function setup() {
  // Setup database schema or seed data
  db.exec(`
    CREATE TABLE IF NOT EXISTS roster (
      id SERIAL PRIMARY KEY,
      given_name VARCHAR(50) NOT NULL,
      family_name VARCHAR(50) NOT NULL
    );
  `);
}

/**
 * The main function that k6 virtual users will execute repeatedly.
 */
export default function() {
  // Perform database operations within the test function
  db.exec(`
    INSERT INTO roster (given_name, family_name)
    VALUES ('Peter', 'Pan'), ('Wendy', 'Darling');
  `);
}

/**
 * Cleans up the rosster table created for the test
 */
export function teardown() {
  db.exec('DROP TABLE IF EXISTS roster;');
  db.close();
}
