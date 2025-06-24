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

import http from 'k6/http';
// import {check, sleep} from 'k6';
import check from 'k6';
import {Trend} from 'k6/metrics';

// A custom trend metric to track the duration of the home page request.
const homePageDuration = new Trend('home_page_duration');

// The options object configures the load profile and performance thresholds
// for the test.
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
  thresholds: {
    // Threshold 1: 95% of all HTTP requests must complete within 500
    // milliseconds.
    // 'http_req_duration': ['p(95)<500'],

    // Threshold 2: 99% of all HTTP requests must complete within 1000
    //  milliseconds.
    // 'http_req_duration': ['p(99)<1000'],

    // Threshold 3: The rate of failed requests must be less than 1%.
    // 'http_req_failed': ['rate<0.01'],

    // Threshold 4: The 95th percentile for our custom home page metric
    // should be below 500ms.
    // 'home_page_duration': ['p(95)<500'],
  },
};

// The base URL of the service under test.
// This defaults to localhost:8080, which is the configured port for the
// book-ui-service. You can override this from the command line,
// e.g., k6 run -e BASE_URL=http://your.host.com performance-test.js

const BASE_URL = __ENV.BASE_URL || 'http://book-ui-svc:80';
/**
 * The main function that k6 virtual users will execute repeatedly.
 */
export default function() {
  // Make a GET request to the application's home page.
  const res = http.get(`${BASE_URL}/`);

  // Add the duration of this specific request to our custom trend metric.
  homePageDuration.add(res.timings.duration);

  // Check the response to ensure it's valid.
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body contains welcome message': (r) =>
      r.body.includes('Welcome to the Book Review System!'),
  });

  // By removing the sleep, each virtual user will send requests as fast as
  // possible. This helps determine the maximum throughput of the application.
  // sleep(1);
}
