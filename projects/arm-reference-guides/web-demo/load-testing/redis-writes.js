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
/* global __ITER */
/* global __VU */

import redis from 'k6/x/redis';
// import {check, sleep} from 'k6';
import check from 'k6';


const REDIS_HOST = __ENV.REDIS_HOST || 'localhost';
const REDIS_PORT = __ENV.REDIS_PORT || '6379';
// If you need redis password
// const REDIS_PASSWORD = __ENV.REDIS_PASSWORD || '';
const REDIS_DB = __ENV.REDIS_DB || '0';

// Define a TTL for the keys created during the test (in seconds)
const KEY_TTL_SECONDS = 300; // Keys will expire after 5 minutes (300 seconds)

const redisClient = new redis.Client(`redis://${REDIS_HOST}:${REDIS_PORT}?db=${REDIS_DB}`);
// If you have a password:
// const redisClient = new redis.Client(`redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}?db=${REDIS_DB}`);

export const options = {
  stages: [
    {duration: '30s', target: 50},
    {duration: '1m', target: 50},
    {duration: '15s', target: 0},
  ],
  // No custom metrics or thresholds, only default k6 metrics will be reported.
  ext: {
    redis: {
      dialTimeout: '5s',
      readTimeout: '3s',
      writeTimeout: '3s',
      poolSize: 100,
    },
  },
};

/**
 * Checks connectivity to Redis
 * The pre-populates the cache with data
 */
export async function setup() {
  console.log('Setting up Redis connection check...');
  const dummyKey = 'k6_redis_connection_test';
  try {
    await redisClient.get(dummyKey);
    console.log(`Successfully connected to Redis. Dummy GET attempted.`);
  } catch (error) {
    if (error.toString().includes('redis: nil')) {
      console.log(`Successfully connected to Redis. Dummy key '${dummyKey}'
        not found (expected behavior).`);
    } else {
      console.error(`Failed to connect to Redis (during dummy GET): ${error}`);
      throw new Error('Redis connection failed in setup!');
    }
  }
  console.log('Redis setup complete. Ready for write operations.');
}

/**
 * Checks connectivity to Redis
 * The pre-populates the cache with data
 */
export default async function() {
  const keyToWrite = `write_test_key_vu_${__VU}_iter_${__ITER}_${Date.now()}`;
  const valueToWrite = `test_value_from_vu_${__VU}
  iter_${__ITER}_${Date.now()}`;

  let success = false;

  try {
    // Perform a SET operation with a TTL
    // Keys will automatically be removed by Redis after KEY_TTL_SECONDS
    await redisClient.set(keyToWrite, valueToWrite,
        KEY_TTL_SECONDS); // <-- TTL implemented here
    success = true;
  } catch (error) {
    console.error(`Failed to SET key ${keyToWrite}: ${error}`);
  }

  check(success, {
    'SET operation successful': (s) => s === true,
  });

  // sleep(0.5); // Still commented out as per your previous instruction
}

/**
 * Checks connectivity to Redis
 * The pre-populates the cache with data
 */
export async function teardown() {
  console.log('Redis teardown complete.');
  console.log(`Note: Keys created during the test ('write_test_key_...')
     have a TTL of ${KEY_TTL_SECONDS} seconds and will expire automatically.`);

  // Optional: Clean up the dummy key used for connection check, as it
  // doesn't have a TTL
  try {
    const dummyKey = 'k6_redis_connection_test';
    await redisClient.del(dummyKey);
    console.log(`Cleaned up dummy key '${dummyKey}'.`);
  } catch (error) {
    // If the dummy key wasn't created or already gone, this might
    // throw 'redis: nil' which is fine
    if (error.toString().includes('redis: nil')) {
      console.log(`Dummy key 'k6_redis_connection_test' not found during
         teardown (already gone or not created).`);
    } else {
      console.error(`Failed to delete dummy key 'k6_redis
        _connection_test': ${error}`);
    }
  }
}
