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

// A trend metric to track the duration of the create review request
//  via the frontend.
const createReviewDuration = new Trend('create_review_duration');

/**
 * The setup function runs once before the test, fetching all book
 *  ISBNs from the catalog service. This ensures our test uses valid
 *  ISBNs that exist in the database.
 *  @return {isbns}
 */
export function setup() {
  console.log('Setting up the test: fetching all book ISBNs...');
  // This URL points to the backend book-catalog-service, which runs on port
  // 8082 by default.
  const catalogUrl = __ENV.CATALOG_URL || 'http://book-catalog-service:80';

  const res = http.get(`${catalogUrl}/api/books/all`);
  if (res.status !== 200) {
    throw new Error(`Could not fetch book ISBNs in setup.
       Status: ${res.status}`);
  }
  const isbns = res.json().map((book) => book.isbn);
  console.log(`Setup complete. Found ${isbns.length} ISBNs to use.`);
  return {isbns: isbns};
}

export const options = {
  stages: [
    {duration: '30s', target: 50},
    {duration: '1m', target: 50},
    {duration: '15s', target: 0},
  ],
  thresholds: {
    // 'http_req_duration': ['p(95)<500'],
    // 'http_req_failed': ['rate<0.01'],
    // 'create_review_duration': ['p(95)<500'],
  },
};

// This URL points to the frontend book-ui-service, which runs on port 8080.
const UI_BASE_URL = __ENV.UI_BASE_URL || 'http://book-ui-svc:80';

/**
 * The main function that k6 virtual users will execute repeatedly.
 * @param {object} data - The data returned from the setup function.
 */
export default function(data) {
  // We can't proceed if we don't have any ISBNs from the setup function
  if (!data.isbns || data.isbns.length === 0) {
    console.error('No ISBNs were loaded from the setup function. VU exiting.');
    return;
  }

  // Pick a random ISBN from the data loaded in the setup function
  const randomIsbn = data.isbns[Math.floor(Math.random() * data.isbns.length)];

  const url = `${UI_BASE_URL}/reviews`;

  // The payload is an object that k6 will automatically convert to
  // x-www-form-urlencoded format.
  const payload = {
    bookIsbn: randomIsbn,
    reviewerName: 'k6 Load Test',
    rating: 5,
    reviewText: 'This is a load test review',
  };

  const params = {
    headers: {
      // The content type must match what the frontend controller expects.
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  };

  const res = http.post(url, payload, params);
  createReviewDuration.add(res.timings.duration);
  check(res, {
    // A successful submission to the UI controller results in a redirect
    // to the book detail page.
    // k6 follows this redirect by default, so the final status should be 200.
    'status is 200': (r) => r.status === 200,
    // We can also verify that we were redirected to the correct book page.
    'redirected to the correct book page': (r) =>
      r.url.includes(`/book/${randomIsbn}`),
  });

  // By removing the sleep, each virtual user will send requests as fast
  // as possible.
  // This helps determine the maximum throughput of the application.
  // sleep(1);
}
