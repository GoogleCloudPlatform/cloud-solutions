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

package com.google.cloud.solutions.dataflow.kafka2bigquery;

import java.io.Serializable;
import java.time.Clock;

/** Clock provider, primarily used in injected fixed time for tests. */
public interface ClockFactory extends Serializable {

  Clock getClock();

  static ClockFactory systemClockFactory() {
    return new SystemClockFactory();
  }

  class SystemClockFactory implements ClockFactory {

    @Override
    public Clock getClock() {
      return Clock.systemUTC();
    }
  }
}
