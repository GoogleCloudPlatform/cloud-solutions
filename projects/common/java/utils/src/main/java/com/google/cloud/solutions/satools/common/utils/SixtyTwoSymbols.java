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

package com.google.cloud.solutions.satools.common.utils;

import com.google.common.annotations.VisibleForTesting;
import com.google.common.base.Preconditions;

/** Provides an implementation to convert a Long to String with 62-symbols (0-9A-Za-z). */
public class SixtyTwoSymbols {

  @VisibleForTesting
  static final char[] SYMBOLS =
      "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz".toCharArray();

  private final long number;

  public SixtyTwoSymbols(Long number) {
    this.number = Preconditions.checkNotNull(number, "number for sixtytwosymbols is null");
  }

  /**
   * Convenience static method to convert a long to String with 62-symbols.
   *
   * @param number the long number to convert to string
   * @return the 62-symbol string representing the number.
   */
  public static String sixtyTwoSymbols(Long number) {
    return new SixtyTwoSymbols(number).convert();
  }

  /** Returns a Base62 string for the given long number. */
  public String convert() {

    var builder = new StringBuilder();
    var quotient = number;

    while (quotient > 0) {
      builder.append(SYMBOLS[(int) (quotient % 62)]);
      quotient /= 62;
    }

    return builder.reverse().toString();
  }
}
