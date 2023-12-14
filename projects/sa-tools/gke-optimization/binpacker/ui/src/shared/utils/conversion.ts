/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Convert given bytes to GiB
 * @param {number} bytes:number
 * @return {number}
 */
export const byteToGiB = (bytes: number): number => {
  return bytes / 1024 / 1024 / 1024;
};

/**
 * Round per 1000 of given GiB memory number
 * @param {number} gib:number
 * @return {number}
 */
export const roundMemoryGib = (gib: number) => {
  return Math.round(gib * 1000) / 1000;
};

/**
 * Convert given bytes number to MiB
 * @param {number} bytes:number
 * @return {number}
 */
export const byteToMiB = (bytes: number): number => {
  return bytes / 1024 / 1024;
};
