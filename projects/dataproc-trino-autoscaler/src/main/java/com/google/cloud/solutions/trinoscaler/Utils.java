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

package com.google.cloud.solutions.trinoscaler;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Message;
import com.google.protobuf.TextFormat;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

/** General utility methods for handling file resources. */
public class Utils {

  /**
   * Reads a JAR resource file as text.
   *
   * @param resourceName the URI of the file in the 'resources` folder
   * @return the contents of the file as text (using UTF_8)
   * @throws IOException when there is error reading the resource file.
   */
  public static String readResourceAsString(String resourceName) throws IOException {
    try (var resourceStream = Utils.class.getClassLoader().getResourceAsStream(resourceName)) {
      return new String(resourceStream.readAllBytes(), StandardCharsets.UTF_8);
    }
  }

  /**
   * Reads the contents of the file as text.
   *
   * @param filePath the file path
   * @return the contents of the file as text (using UTF_8)
   * @throws IOException when there is error reading the resource file.
   */
  public static String readFileAsString(String filePath) throws IOException {
    return Files.readString(Paths.get(filePath));
  }

  /**
   * Reads the content of the file as Text Protobuf.
   *
   * <p>Parses the text file as per the Protocol Buffer class specified using <a
   * href="https://protobuf.dev/reference/protobuf/textformat-spec/">Text format</a>.
   *
   * @param pbClass the Protobuf class definition for the filecontents
   * @param filePath the path to the text file
   * @return The protobuf object parsed from the text file.
   * @throws IOException when there is error reading the resource file.
   */
  public static <T extends Message> T readFileAsPb(Class<T> pbClass, String filePath)
      throws IOException {
    return TextFormat.parse(readFileAsString(filePath), pbClass);
  }

  /**
   * Returns an {@link com.google.common.collect.ImmutableList} from the given list.
   *
   * <p>The returned list is empty if {@code list} is null or empty.
   *
   * @param list the list to convert
   */
  public static <T> ImmutableList<T> emptyOrImmutableList(List<T> list) {
    return (list == null) ? ImmutableList.of() : ImmutableList.copyOf(list);
  }

  private Utils() {}
}
