/*
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.google.cloud.solutions.dataflow.kafka2bigquery.testing;

import com.google.cloud.solutions.dataflow.kafka2bigquery.ClockFactory;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

/** Provides a fixed time Clock for testing. */
public final class FixedTimeClockFactory implements ClockFactory {

  private final String fixedTime;

  /**
   * Creates a fixed time clockFactory for testing.
   *
   * @param fixedTime The ISO instant formatter in UTC, such as '2011-12-03T10:15:30Z'.
   */
  public FixedTimeClockFactory(String fixedTime) {
    this.fixedTime = fixedTime;
  }

  @Override
  public Clock getClock() {
    return Clock.fixed(Instant.parse(fixedTime), ZoneOffset.UTC);
  }
}
