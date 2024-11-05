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

package com.google.cloud.solutions.satools.common.testing;

import com.google.common.truth.Truth;
import org.checkerframework.checker.nullness.qual.Nullable;

/** A configurable Assert that allows injecting arbitrary assertion and validation logic. */
public interface AssertValidator<T> {

  void validate(@Nullable T actual);

  /**
   * Default AssertionValidator that checks if actual value {@link
   * com.google.common.truth.Truth#assertThat} equals the expected value.
   */
  class DefaultAssertValidator<T> implements AssertValidator<T> {
    private final T expected;

    public DefaultAssertValidator(@Nullable T expected) {
      this.expected = expected;
    }

    @Override
    public void validate(@Nullable T actual) {
      Truth.assertThat(actual).isEqualTo(expected);
    }
  }
}
