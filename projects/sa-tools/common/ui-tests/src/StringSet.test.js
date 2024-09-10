/*
 * Copyright 2023 Google LLC
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

import {describe, expect, it} from 'vitest';
import {StringSet} from './Common/StringSet';

/**
 * Assert StringSet equality to an array.
 * @param {any} set
 * @param {any} expectedArray
 */
function assertEquals(set, expectedArray) {
  expect(set.toArray()).toEqual(expectedArray);
}

const stringSetTest = () => {
  it('init single value', () => assertEquals(new StringSet('a'), ['a']));

  it('init array', () => assertEquals(new StringSet(['a', 'b']), ['a', 'b']));

  it(`doesn't add duplicate single value`, () =>
    assertEquals(new StringSet(['a', 'b']).add('a'), ['a', 'b']));

  it(`doesn't addAll duplicates`, () =>
    assertEquals(new StringSet(['a', 'b']).addAll(['a', 'b', 'c']), [
      'a',
      'b',
      'c',
    ]));

  it('removes item (single)', () =>
    assertEquals(new StringSet(['a', 'b']).remove('a'), ['b']));

  it('removes item (array)', () =>
    assertEquals(new StringSet(['a', 'b']).removeAll(['a', 'b']), []));

  it('removes non-existing item (single)', () =>
    assertEquals(new StringSet(['a', 'b']).remove('c'), ['a', 'b']));

  it('removes non-existing item (array)', () =>
    assertEquals(new StringSet(['a', 'b']).removeAll(['c', 'a']), ['b']));
};

describe('StringSet test suite', stringSetTest);
