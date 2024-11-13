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

import com.google.common.base.Splitter;
import com.google.common.flogger.GoogleLogger;
import com.google.common.io.ByteStreams;
import com.google.common.io.Files;
import java.io.File;
import java.io.IOException;
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
public final class DynamicClassLoader {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  /**
   * Utility method that copies each of the user provided Proto JAR to the worker and creates a new
   * URLClassLoader pointing to the URLs for the localized JAR dependencies.
   *
   * <p>Parts of this class are copied from <a
   * href="https://github.com/GoogleCloudPlatform/DataflowTemplates/blob/4fb83d3608f8344da149e72668b68702f17b134a/v2/googlecloud-to-googlecloud/src/main/java/com/google/cloud/teleport/v2/io/DynamicJdbcIO.java#L288">DynamicJDBCIO</a>
   */
  public static URLClassLoader getNewClassLoader(String paths) {
    List<String> listOfJarPaths = Splitter.on(',').trimResults().splitToList(paths);

    final String destRoot = Files.createTempDir().getAbsolutePath();
    URL[] urls =
        listOfJarPaths.stream()
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
                    throw new RuntimeException(ex);
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
