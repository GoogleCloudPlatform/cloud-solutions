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

import redis from 'k6/x/redis';
// import {check, sleep} from 'k6';
import check from 'k6';

const REDIS_HOST = __ENV.REDIS_HOST || 'localhost';
const REDIS_PORT = __ENV.REDIS_PORT || '6379';
// If you have a password use it below
// const REDIS_PASSWORD = __ENV.REDIS_PASSWORD || '';
const REDIS_DB = __ENV.REDIS_DB || '0';

const KEY_PREFIX = 'my_data_key_';
const NUM_KEYS_TO_PREPARE = 1000;

const redisClient = new redis.Client(`redis://${REDIS_HOST}:${REDIS_PORT}?db=${REDIS_DB}`);
// If you have a password:
// const redisClient = new redis.Client(`redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}?db=${REDIS_DB}`);

export const options = {
  stages: [
    {duration: '30s', target: 50},
    {duration: '1m', target: 50},
    {duration: '15s', target: 0},
  ],
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
  console.log('Setting up Redis data...');
  // Confirm Redis connectivity by performing a non-destructive
  //  GET on a dummy key
  const dummyKey = 'k6_redis_connection_test'; // FIX: Declare dummyKey here
  try {
    // Attempt to GET the dummy key.
    await redisClient.get(dummyKey);
    console.log(`Successfully connected to Redis. Dummy GET attempted.`);
  } catch (error) {
    // Specifically check for the "redis: nil" error, which means key not
    // found (and connection is okay)
    if (error.toString().includes('redis: nil')) {
      console.log(`Successfully connected to Redis.
        Dummy key '${dummyKey}' not found (expected behavior).`);
    } else {
      // If it's any other error, then it's a true connection issue
      console.error(`Failed to connect to Redis (during dummy GET): ${error}`);
      throw new Error('Redis connection failed in setup!');
    }
  }

  // Pre-populate Redis with some data to read
  for (let i = 0; i < NUM_KEYS_TO_PREPARE; i++) {
    const key = `${KEY_PREFIX}${i}`;
    const value = `value_for_key_${i}_at_${Date.now()}`;
    try {
      await redisClient.set(key, value, 0);
    } catch (error) {
      console.error(`Failed to set key ${key}: ${error}`);
      throw error;
    }
  }
  console.log(`Pre-populated ${NUM_KEYS_TO_PREPARE} keys in Redis.`);
}

/**
 * Default function run during test
 * Checks for keys in Redis
 */
export default async function() {
  const randomKeyIndex = Math.floor(Math.random() * NUM_KEYS_TO_PREPARE);
  const keyToRead = `${KEY_PREFIX}${randomKeyIndex}`;

  let value;
  let success = false;

  try {
    value = await redisClient.get(keyToRead);
    success = true;
  } catch (error) {
    console.error(`Failed to GET key ${keyToRead}: ${error}`);
  }

  check(value, {
    'GET operation successful': (v) => success === true,
    'returned value is not null': (v) => v !== null,
    'returned value is a string': (v) => typeof v === 'string',
    [`value for ${keyToRead} matches prefix`]: (v) => v ?
     v.startsWith(`value_for_key_${randomKeyIndex}`) : false,
  });

  // sleep(0.5);
}

/**
 * Default function run during test
 * Checks for keys in Redis
 */
export async function teardown() {
  console.log('Cleaning up Redis data...');
  for (let i = 0; i < NUM_KEYS_TO_PREPARE; i++) {
    const key = `${KEY_PREFIX}${i}`;
    try {
      await redisClient.del(key);
    } catch (error) {
      console.error(`Failed to DEL key ${key}:
        ${error}`);
    }
  }
  console.log(`Cleaned up ${NUM_KEYS_TO_PREPARE} keys from Redis.`);
}
