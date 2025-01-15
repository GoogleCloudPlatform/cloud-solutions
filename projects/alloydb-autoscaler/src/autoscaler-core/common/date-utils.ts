/**
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

/** @fileoverview Provides utilities to deal with dates and timestamps. */

/** Milliseconds in one minute. */
export const MS_IN_1_MIN = 60 * 1000;

/**
 * Formats duration as human-readable text.
 *
 * @param milliseconds Duration in milliseconds.
 * @return Duration converted to human readable.
 */
export function convertMillisecondsToHumanReadable(
  milliseconds: number
): string {
  if (milliseconds < 0) return '0.0 Sec';

  const seconds = milliseconds / 1000;
  if (seconds < 60) return seconds.toFixed(1) + ' Sec';

  const minutes = seconds / 60;
  if (minutes < 60) return minutes.toFixed(1) + ' Min';

  const hours = minutes / 60;
  if (hours < 24) return hours.toFixed(1) + ' Hrs';

  const days = hours / 24;
  return days.toFixed(1) + ' Days';
}
