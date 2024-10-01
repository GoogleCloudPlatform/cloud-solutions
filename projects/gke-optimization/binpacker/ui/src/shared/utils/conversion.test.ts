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
import {test, expect} from 'vitest';
import {byteToGiB, byteToMiB, roundMemoryGib} from './conversion';

test('byteToGiB', () => {
  expect(byteToGiB(1073741824)).toBe(1);
  expect(byteToGiB(1610612736)).toBe(1.5);
  expect(byteToGiB(8589934592)).toBe(8);
});

test('byteToMiB', () => {
  expect(byteToMiB(1048576)).toBe(1);
  expect(byteToMiB(2621440)).toBe(2.5);
  expect(byteToMiB(10485760)).toBe(10);
});

test('roundMemoryGib', () => {
  expect(roundMemoryGib(1)).toBe(1);
  expect(roundMemoryGib(0.0009)).toBe(0.001);
  expect(roundMemoryGib(0.5554)).toBe(0.555);
  expect(roundMemoryGib(0.5555)).toBe(0.556);
  expect(roundMemoryGib(1.9999)).toBe(2);
});
