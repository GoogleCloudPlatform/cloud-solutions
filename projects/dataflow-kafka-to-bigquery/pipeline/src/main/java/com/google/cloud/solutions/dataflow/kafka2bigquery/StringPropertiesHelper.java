/*
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

package com.google.cloud.solutions.dataflow.kafka2bigquery;

import com.google.common.flogger.GoogleLogger;
import java.io.IOException;
import java.io.StringReader;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.stream.Collectors;

/** Allows Reading properties from a String. */
public final class StringPropertiesHelper {
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final String propertiesString;

  public StringPropertiesHelper(String propertiesString) {
    this.propertiesString = propertiesString;
  }

  public StringPropertiesHelper(List<String> lines) {
    this(lines.stream().collect(Collectors.joining("\n")));
  }

  /** Reads the properties string as a Map. */
  public Map<String, Object> readAsMap() {
    try {
      var properties = new Properties();
      properties.load(new StringReader(propertiesString));
      return properties.entrySet().stream()
          .collect(Collectors.toMap(entry -> entry.getKey().toString(), Map.Entry::getValue));
    } catch (IOException ioException) {
      logger.atSevere().withCause(ioException).log("unable to read the properties");
    }

    return Map.of();
  }

  public static StringPropertiesHelper create(String propertiesString) {
    return new StringPropertiesHelper(propertiesString);
  }

  public static StringPropertiesHelper create(List<String> propertiesLines) {
    return new StringPropertiesHelper(propertiesLines);
  }
}
