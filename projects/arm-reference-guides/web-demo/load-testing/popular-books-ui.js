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

// A trend metric to track the duration of the "Popular Books" page request.
const popularBooksDuration = new Trend('popular_books_duration');

export const options = {
  stages: [
    {duration: '30s', target: 50},
    {duration: '1m', target: 50},
    {duration: '15s', target: 0},
  ],
  thresholds: {
    // 'http_req_duration': ['p(95)<500'],
    // 'http_req_failed': ['rate<0.01'],
    // 'popular_books_duration': ['p(95)<500'],
  },
};

const UI_BASE_URL = __ENV.UI_BASE_URL || 'http://book-ui-svc:80';

/**
 * The main function that k6 virtual users will execute repeatedly.
 */
export default function() {
  const res = http.get(`${UI_BASE_URL}/books/popular`);
  popularBooksDuration.add(res.timings.duration);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body contains "Popular Books"': (r) =>
      r.body.includes('Popular Books (from Redis)'),
  });
  // By removing the sleep, each virtual user will send requests as fast
  // as possible. This helps determine the maximum throughput
  // of the application.
  // sleep(1);
}
