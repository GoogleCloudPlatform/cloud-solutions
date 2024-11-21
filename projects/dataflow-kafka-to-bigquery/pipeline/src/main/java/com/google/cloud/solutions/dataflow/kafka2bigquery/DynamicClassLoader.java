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

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;

import autovalue.shaded.com.google.common.collect.ImmutableList;
import com.google.common.base.Splitter;
import com.google.common.flogger.GoogleLogger;
import com.google.common.io.ByteStreams;
import com.google.common.io.Files;
import java.io.File;
import java.io.IOException;
import java.io.Serializable;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.channels.ReadableByteChannel;
import java.nio.channels.WritableByteChannel;
import java.nio.file.Paths;
import java.util.List;
import org.apache.beam.sdk.io.FileSystems;
import org.apache.beam.sdk.io.fs.ResourceId;
import org.apache.beam.sdk.util.MimeTypes;

/** Stages JARs from GCS location to Dataflow worker for loading classes dynamically. */
public final class DynamicClassLoader implements Serializable {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final ImmutableList<String> jarPaths;

  private DynamicClassLoader(List<String> jarPaths) {
    checkNotNull(jarPaths, "jarPaths should not be null");
    checkArgument(!jarPaths.isEmpty(), "Provide at least 1 jarPath");
    this.jarPaths = ImmutableList.copyOf(jarPaths);
  }

  public static DynamicClassLoader from(String jarPathsCsv) {
    var paths = Splitter.on(',').trimResults().splitToList(jarPathsCsv);
    return new DynamicClassLoader(paths);
  }

  /**
   * Loads class from the provided JAR file and verifies if the class is of provided type.
   *
   * @param className the name of the class to load
   * @param expectedType the type/supertype of the class
   * @return the class type-casted as the {@code expectedType}
   * @param <T> the type of the expected class
   */
  @SuppressWarnings("unchecked") // protoClass is verified to be a Message class
  public <T> Class<T> loadClass(String className, Class<T> expectedType) {
    try {
      var classLoader = getNewClassLoader();
      var clazz = classLoader.loadClass(className);

      checkArgument(
          expectedType.isAssignableFrom(clazz),
          "Provided class (%s) is not of type: %s",
          clazz,
          expectedType);

      return (Class<T>) clazz;
    } catch (ClassNotFoundException e) {
      logger.atSevere().withCause(e).log("class %s, not found in %s", className, jarPaths);
      throw new RuntimeException("error loading class", e);
    }
  }

  /**
   * Utility method that copies each of the user provided Proto JAR to the worker and creates a new
   * URLClassLoader pointing to the URLs for the localized JAR dependencies.
   *
   * <p>Parts of this class are copied from <a
   * href="https://github.com/GoogleCloudPlatform/DataflowTemplates/blob/4fb83d3608f8344da149e72668b68702f17b134a/v2/googlecloud-to-googlecloud/src/main/java/com/google/cloud/teleport/v2/io/DynamicJdbcIO.java#L288">DynamicJDBCIO</a>
   */
  private URLClassLoader getNewClassLoader() {

    final String destRoot = Files.createTempDir().getAbsolutePath();
    URL[] urls =
        jarPaths.stream()
            .map(
                jarPath -> {
                  try {
                    ResourceId sourceResourceId = FileSystems.matchNewResource(jarPath, false);
                    File destFile = Paths.get(destRoot, sourceResourceId.getFilename()).toFile();

                    ResourceId destResourceId =
                        FileSystems.matchNewResource(destFile.getAbsolutePath(), false);

                    copy(sourceResourceId, destResourceId);
                    logger.atInfo().log(
                        "Localized jar: %s to: %s", sourceResourceId, destResourceId);

                    return destFile.toURI().toURL();
                  } catch (IOException ex) {
                    throw new RuntimeException("error loading class dynamically", ex);
                  }
                })
            .toArray(URL[]::new);

    return URLClassLoader.newInstance(urls);
  }

  private static void copy(ResourceId source, ResourceId dest) throws IOException {
    try (ReadableByteChannel rbc = FileSystems.open(source)) {
      try (WritableByteChannel wbc = FileSystems.create(dest, MimeTypes.BINARY)) {
        ByteStreams.copy(rbc, wbc);
      }
    }
  }
}
