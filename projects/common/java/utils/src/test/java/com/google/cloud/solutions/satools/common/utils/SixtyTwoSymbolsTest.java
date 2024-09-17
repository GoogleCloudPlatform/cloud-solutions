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

import static com.google.common.truth.Truth.assertThat;

import java.util.stream.IntStream;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

/** Provides a custom implementation to convert a long number to a 62 symbol string. */
public class SixtyTwoSymbolsTest {

  @Test
  public void init_validSymbolList() {

    var expectedCharArray =
        Stream.of(
                IntStream.range(0, 10).mapToObj(i -> (char) ('0' + i)),
                IntStream.range(0, 26).mapToObj(i -> (char) ('A' + i)),
                IntStream.range(0, 26).mapToObj(i -> (char) ('a' + i)))
            .reduce(Stream::concat)
            .orElseGet(Stream::empty)
            .toArray();

    assertThat(SixtyTwoSymbols.SYMBOLS)
        .asList()
        .containsExactlyElementsIn(expectedCharArray)
        .inOrder();
  }

  @ParameterizedTest
  @MethodSource("sixtyTwoTestCases")
  public void sixtyTwoSymbols_valid(Long input, String expected62String) {
    assertThat(SixtyTwoSymbols.sixtyTwoSymbols(input)).isEqualTo(expected62String);
  }

  public static Stream<Arguments> sixtyTwoTestCases() {
    return Stream.of(Arguments.of(123L, "1z"), Arguments.of(9876543210L, "AmOy42"));
  }
}
