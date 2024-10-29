/*
 * Copyright (C) 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

package com.google.cloud.solutions.dataflow.avrotospannerscd.utils;

import java.io.Serializable;
import java.time.Clock;

/** Clock Factory provides Clock instances. */
public interface ClockFactory extends Serializable {
  Clock getClock();

  /** Default Clock Factory using System UTC time. */
  class SystemUtcClockFactory implements ClockFactory {

    /** Creates a new ClockFactory. */
    public static ClockFactory create() {
      return new SystemUtcClockFactory();
    }

    /** Gets a Clock instance using UTC time. */
    @Override
    public Clock getClock() {
      return Clock.systemUTC();
    }
  }
}
