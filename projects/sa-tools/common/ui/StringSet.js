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

/**
 * Checks if an object is not a valid array.
 *
 * @param {?any}values
 * @return {boolean}
 */
function isInvalidArray(values) {
  return !values || !Array.isArray(values) || values.length === 0;
}

/**
 * Provides a thin wrapper on top of ES6 Set
 */
class StringSet {
  /**
   * StringSet constructor.
   *
   * @param {any} initSet
   */
  constructor(initSet) {
    this.set = new Set(initSet);
  }

  /**
   * Returns the elements in the Set as string array.
   *
   * @return {string[]}
   */
  toArray() {
    return Array.from(this.set);
  }

  /**
   * Add a string to the set
   *
   * @param {?string} value
   * @return {StringSet}
   */
  add(value) {
    if (!value) {
      return this;
    }

    this.set.add(value);
    return this;
  }

  /**
   * Add all values of the array to the set.
   *
   * @param {any} values
   * @return {StringSet}
   */
  addAll(values) {
    if (isInvalidArray(values)) {
      return this;
    }

    values.forEach((value) => this.add(value));
    return this;
  }

  /**
   * remove a value from set
   *
   * @param {?string} value
   * @return {StringSet}
   */
  remove(value) {
    if (!value) {
      return this;
    }

    this.set.delete(value);
    return this;
  }

  /**
   * Same as `remove`
   *
   * @param {?string} value
   * @return {StringSet}
   */
  delete(value) {
    return this.remove(value);
  }

  /**
   * Remove all elements of the array from the set.
   *
   * @param {any} values
   * @return {any}
   */
  removeAll(values) {
    if (isInvalidArray(values)) {
      return this;
    }

    values.forEach((value) => this.remove(value));
    return this;
  }
}

export {StringSet};
