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

package com.google.cloud.solutions.dataflow.kafka2bigquery.testing;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.api.client.json.GenericJson;
import com.google.api.services.bigquery.model.DatasetReference;
import com.google.api.services.bigquery.model.TableReference;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

public class GenericJsonStringifier {
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  public static LinkedHashMap<String, String> convertMapEntriesToString(
      Map<? extends GenericJson, ? extends GenericJson> map) {
    if (map == null) {
      return null;
    }

    var stringMapBuilder = new LinkedHashMap<String, String>();
    for (var entry : map.entrySet()) {
      var key = convertObjectToString(entry.getKey());
      var value = convertObjectToString(entry.getValue());

      if (key == null) {
        continue;
      }

      stringMapBuilder.put(key, value);
    }

    return stringMapBuilder;
  }

  public static LinkedHashSet<String> convertSetToString(Set<? extends GenericJson> set) {
    if (set == null) {
      return null;
    }

    var stringSetBuilder = new LinkedHashSet<String>();
    for (var entry : set) {
      var value = convertObjectToString(entry);
      if (value == null) {
        continue;
      }
      stringSetBuilder.add(value);
    }

    return stringSetBuilder;
  }

  public static String convertAndAddToCollection(GenericJson json, Collection<String> collection) {

    var stringValue = convertObjectToString(json);

    if (collection == null || stringValue == null) {
      return stringValue;
    }

    collection.add(stringValue);
    return stringValue;
  }

  public static <T extends GenericJson> String convertObjectToString(T json) {
    try {

      if (json instanceof DatasetReference dataset) {
        return String.format("%s.%s", dataset.getProjectId(), dataset.getDatasetId());
      } else if (json instanceof TableReference table) {
        return String.format(
            "%s.%s.%s", table.getProjectId(), table.getDatasetId(), table.getTableId());
      }

      return new ObjectMapper().writeValueAsString(json);
    } catch (JsonProcessingException e) {
      logger.atSevere().withCause(e).withStackTrace(StackSize.MEDIUM).log("Error parsing %s", json);
    }
    return null;
  }

  public static <T extends GenericJson> T convertJsonToObject(String json, Class<T> jsonClass) {
    try {
      if (json == null || jsonClass == null) {
        return null;
      }

      var mapper = new ObjectMapper();
      return mapper.readValue(json, jsonClass);
    } catch (JsonProcessingException e) {
      logger.atSevere().withCause(e).withStackTrace(StackSize.MEDIUM).log("Error parsing %s", json);
    }
    return null;
  }

  private GenericJsonStringifier() {}
}
