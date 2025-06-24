/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
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
// import {check, sleep} from 'k6';
import check from 'k6';

const DB_USER = __ENV.DB_USER;
const DB_PASSWORD = __ENV.DB_PASSWORD;
const DB_HOST = __ENV.DB_HOST;
const DB_PORT = __ENV.DB_PORT;
const DB_NAME = __ENV.DB_NAME;

export const options = {
  stages: [
    {duration: '30s', target: 50},
    {duration: '1m', target: 50},
    {duration: '15s', target: 0},
  ],
  thresholds: {
    //  'sql_query_duration{query_type:select}': ['p(95)<200ms'],
  },
};

const db = sql.open(driver, `postgres://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable`);

/**
 * The setup function runs once before the test, fetching all book
 *  ISBNs from the catalog service. This ensures our test uses valid
 *  ISBNs that exist in the database.
 *  @log Success or Error
 */
export function setup() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS roster (
      id SERIAL PRIMARY KEY,
      given_name VARCHAR(50) NOT NULL,
      family_name VARCHAR(50) NOT NULL
    );
  `);

  const res = db.query('SELECT COUNT(*) FROM roster;');
  if (res[0].count === 0) {
    db.exec(`
      INSERT INTO roster (given_name, family_name)
      VALUES
        ('Peter', 'Pan'),
        ('Wendy', 'Darling'),
        ('Captain', 'Hook'),
        ('Tiger', 'Lily'),
        ('Smee', 'Smee');
    `);
    console.log('Initial data inserted into roster table.');
  } else {
    console.log('Roster table already contains data, skipping initial insert.');
  }
}

/**
 * The main function that k6 virtual users will execute repeatedly.
 */
export default function() {
  const result = db.query('SELECT id, given_name, family_name FROM roster;');

  check(result, {
    'rows are returned': (r) => r.length > 0,
    'at least 2 rows returned': (r) => r.length >= 2,
  });

  // sleep(1);

  const idToQuery = Math.floor(Math.random() * 5) + 1;
  // FIX: Pass the variable directly, not wrapped in an array.
  const singleResult = db.query(`SELECT given_name FROM roster
    WHERE id = $1;`, idToQuery);

  check(singleResult, {
    'single row returned for specific ID': (r) => r.length === 1,
  });

  // sleep(0.5);
}

/**
 * This function cleans up the roster table created for the test
 */
export function teardown() {
  db.exec('DROP TABLE IF EXISTS roster;');
  db.close();
  console.log('Roster table dropped and database connection closed.');
}
