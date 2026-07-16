/**
 * Copyright 2026 Google LLC
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

import {Pool, QueryResult} from 'pg';
import * as _ from 'lodash';

/**
 * Required ENV variables to be set:

    PGPORT=5432
    PGDATABASE=
    PGUSER=postgres
    PGHOST=
    PGPASSWORD=
 */

/**
 * Converts SQL field names from snake_case to camelCase.
 *
 * @param rows Rows from a database query
 * @returns
 */
export const camelCaseRows = (rows: Record<string, unknown>[]) =>
  _.map(rows, row => _.mapKeys(row, (_value, key) => _.camelCase(key)));

/**
 * Escapes single quotes in a string.
 *
 * @param str String to be escaped
 * @returns escaped string
 */
export const safeString = (str: string) => str?.replace(/'/g, "''") ?? '';

// Add SelectedFacets type (optional but good practice)
export type SelectedFacets = {[key: string]: string[]};

// --- Helper to interpolate query parameters for display ---
export function interpolateQuery(queryText: string, params: unknown[]): string {
  if (params && params.length === 0) {
    return queryText; // No params to process for display
  } else {
    let interpolatedQuery = queryText;
    // Handle parameters in reverse order ($10 before $1) to avoid replacing $1 in $10
    for (let i = params.length - 1; i >= 0; i--) {
      const value = params[i];
      let formattedValue: string;

      // Format based on type for SQL literal representation
      if (value === null || typeof value === 'undefined') {
        formattedValue = 'NULL';
      } else if (typeof value === 'string') {
        // Escape single quotes within the string
        formattedValue = `'${value.replace(/'/g, "''")}'`;
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        formattedValue = String(value);
      } else if (value instanceof Date) {
        formattedValue = `'${value.toISOString()}'`; // Standard ISO format
      } else if (Array.isArray(value)) {
        // Format as PostgreSQL array literal, handling types within the array
        const arrayValues = value
          .map(item => {
            if (item === null || typeof item === 'undefined') return 'NULL';
            if (typeof item === 'string')
              return `'${item.replace(/'/g, "''")}'`;
            if (typeof item === 'number' || typeof item === 'boolean')
              return String(item);
            if (item instanceof Date) return `'${item.toISOString()}'`;
            // Fallback for other types - might need adjustment
            return `'${String(item).replace(/'/g, "''")}'`;
          })
          .join(', ');
        formattedValue = `ARRAY[${arrayValues}]`;
      } else {
        // Fallback for unknown types (treat as string with escaping)
        formattedValue = `'${String(value).replace(/'/g, "''")}'`;
      }

      // Replace the placeholder - use regex to ensure whole placeholder match
      // Using a regex like /\$N\b/ (word boundary) avoids replacing $1 in $10, $11 etc.
      const placeholderRegex = new RegExp(`\\$${i + 1}\\b`, 'g');
      interpolatedQuery = interpolatedQuery.replace(
        placeholderRegex,
        formattedValue
      );
    }
    return interpolatedQuery;
  }
}

export class Database {
  private pool: Pool;

  constructor() {
    if (!process.env['PGHOST']) {
      throw new Error("Missing required environment variable: 'PGHOST'");
    }
    this.pool = new Pool({
      user: 'postgres',
      // Explicitly pass other connection details from environment variables
      host: process.env.PGHOST,
      database: process.env.PGDATABASE,
      password: process.env.PGPASSWORD,
      port: parseInt(process.env.PGPORT || '5432', 10),

      // --- CRITICAL CONFIGURATIONS TO PREVENT ECONNRESET ---

      // How long a client is allowed to remain idle before being closed
      // Set this to a value less than your database/proxy's idle timeout.
      // A good starting point is 30 seconds (30000 milliseconds).
      idleTimeoutMillis: 30000,

      // How long to wait for a connection to be established.
      // A value of 10-20 seconds is reasonable.
      connectionTimeoutMillis: 20000,

      // Enable TCP Keep-Alive to prevent intermediate network devices from
      // dropping idle connections.
      keepAlive: true,

      // Frequency of TCP Keep-Alive probes. Default is often sufficient.
      // keepAliveInitialDelayMillis: 0, // Defaults to 0
    });

    // the pool will emit an error on behalf of any idle clients
    // it contains if a backend error or network partition happens
    this.pool.on('error', err => {
      console.error('Unexpected error on idle client', err);
      // It's generally not recommended to throw here as it can crash the process.
      // The pool will automatically remove the faulty client.
    });

    this.pool.on('connect', () => {
      console.log('A new client has connected to the database.');
    });

    this.pool.on('remove', () => {
      console.log('A client has been removed from the pool.');
    });
  }

  // Query method (for non-parameterized queries like CREATE EXTENSION)
  async query(queryText: string): Promise<Record<string, unknown>[]> {
    console.log(
      'Running raw query in non-PSV pool:',
      queryText.substring(0, 100) + '...'
    );
    try {
      const res = await this.pool.query(queryText);
      return res.rows;
    } catch (err) {
      console.error(
        `Error executing raw query: ${queryText.substring(0, 100)}...`,
        err
      );
      throw err; // Re-throw after logging
    }
  }

  // --- Method for Parameterized Queries ---
  async queryWithParams(
    queryText: string,
    params: unknown[]
  ): Promise<Record<string, unknown>[]> {
    console.log(
      `Running parameterized query in non-PSV pool: ${queryText.substring(0, 100)}... with ${params.length} params`
    );
    try {
      const res: QueryResult = await this.pool.query(queryText, params);
      return res.rows;
    } catch (err) {
      console.error(
        `Error executing parameterized query: ${queryText.substring(0, 100)}... with params: ${JSON.stringify(params)}`,
        err
      );
      throw err; // Re-throw after logging
    }
  }

  async end() {
    await this.pool.end();
  }
}
