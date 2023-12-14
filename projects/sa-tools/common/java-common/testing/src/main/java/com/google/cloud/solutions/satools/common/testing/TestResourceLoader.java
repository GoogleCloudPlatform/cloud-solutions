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

import com.google.cloud.solutions.satools.common.utils.ProtoUtils;
import com.google.common.flogger.GoogleLogger;
import com.google.common.io.Files;
import com.google.common.io.Resources;
import com.google.gson.Gson;
import com.google.protobuf.Message;
import com.google.protobuf.TextFormat;
import com.google.protobuf.TextFormat.ParseException;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileFilter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Type;
import java.net.MalformedURLException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import org.apache.commons.io.filefilter.WildcardFileFilter;

/**
 * Supports loading testing files and decoding into formats like String, Proto and AVRO for ease in
 * writing unit tests.
 */
public interface TestResourceLoader {

  URL loadResource(String resourcePath) throws MalformedURLException;

  default List<String> loadResourcesLike(String baseDir, String resourcePattern)
      throws MalformedURLException {
    throw new UnsupportedOperationException();
  }

  /** Returns the loaded resource as text string using UTF_8 Character set. */
  default String loadResourceAsString(String resourcePath) throws IOException {

    try (var reader =
        new BufferedReader(
            new InputStreamReader(
                loadResource(resourcePath).openStream(), StandardCharsets.UTF_8))) {
      return reader.lines().collect(Collectors.joining("\n"));
    }
  }

  default InputStream loadResourceInputStream(String resourcePath) throws IOException {
    return loadResource(resourcePath).openStream();
  }

  /** Load the given resource by parsing as text. */
  default String loadAsString(String resourcePath) {
    try {
      return loadResourceAsString(resourcePath);
    } catch (IOException ioException) {
      throw new ResourceLoadException(resourcePath, ioException);
    }
  }

  /** Provide a resource loader that uses absolute paths to parse the resource location. */
  static ResourceActions absolutePath() {
    return new ResourceActions(
        new TestResourceLoader() {
          @Override
          public URL loadResource(String resourcePath) throws MalformedURLException {
            return new File(resourcePath).toURI().toURL();
          }

          @Override
          public List<String> loadResourcesLike(String baseDir, String resourcePattern) {
            var files =
                new File(baseDir).listFiles((FileFilter) new WildcardFileFilter(resourcePattern));

            if (files != null && files.length > 0) {
              return Arrays.stream(files).map(File::toString).toList();
            }
            return List.of();
          }
        });
  }

  static ResourceActions classPath() {
    return new ResourceActions(Resources::getResource);
  }

  /** All the actions that can be taken on any test resource. */
  final class ResourceActions {

    private final TestResourceLoader resourceLoader;

    private ResourceActions(TestResourceLoader resourceLoader) {
      this.resourceLoader = resourceLoader;
    }

    public String loadAsString(String resourceUri) {
      return resourceLoader.loadAsString(resourceUri);
    }

    public <T> T loadAsJson(String resourceUri, Type jsonClass) {
      return new Gson().fromJson(loadAsString(resourceUri), jsonClass);
    }

    /**
     * Returns actions to perform on the resource by parsing the resource as a Protobuf object of
     * the {@code protoClazz}.
     */
    public <T extends Message> ProtoActions<T> forProto(Class<T> protoClazz) {
      return new ProtoActions<>() {
        @Override
        public T loadJson(String jsonProtoFile) {
          return ProtoUtils.parseProtoJson(resourceLoader.loadAsString(jsonProtoFile), protoClazz);
        }

        @Override
        public T loadText(String textProtoFile) {
          try {
            return TextFormat.parse(resourceLoader.loadAsString(textProtoFile), protoClazz);
          } catch (ParseException parseException) {
            return null;
          }
        }

        @Override
        public List<T> loadAllTextFiles(List<String> textPbFiles) {
          return textPbFiles.stream().map(this::loadText).toList();
        }

        @Override
        public List<T> loadAllTextFiles(String... textPbFiles) {
          return loadAllTextFiles(List.copyOf(Arrays.asList(textPbFiles)));
        }

        @Override
        public List<T> loadAllJsonFiles(List<String> jsonPbFiles) {
          return jsonPbFiles.stream().map(this::loadJson).toList();
        }

        @Override
        public List<T> loadAllJsonFiles(String jsonPbFile, String... otherJsonPbFiles) {

          var fileListBuilder = new ArrayList<String>();

          if (otherJsonPbFiles != null && otherJsonPbFiles.length > 0) {
            fileListBuilder.addAll(Arrays.asList(otherJsonPbFiles));
          }

          return loadAllJsonFiles(List.copyOf(fileListBuilder));
        }

        @Override
        public List<T> loadAllJsonFilesLike(String baseDir, String filePattern) {
          try {
            return resourceLoader.loadResourcesLike(baseDir, filePattern).stream()
                .map(this::loadJson)
                .toList();
          } catch (MalformedURLException malformedUrlException) {
            GoogleLogger.forEnclosingClass()
                .atSevere()
                .withCause(malformedUrlException)
                .log("Loading error with FilePattern: %s", filePattern);
          }

          return List.of();
        }
      };
    }

    /** Returns a resource copying implementation to copy the resource to the provided folder. */
    public CopyActions copyTo(File folder) {
      return resourcePath -> {
        var outputFile = File.createTempFile("temp_", "", folder);

        long copiedBytes =
            Files.asByteSink(outputFile)
                .writeFrom(resourceLoader.loadResourceInputStream(resourcePath));

        GoogleLogger.forEnclosingClass()
            .atInfo()
            .log(
                "Copied %s bytes from %s to %s",
                copiedBytes, resourcePath, outputFile.getAbsolutePath());

        return outputFile;
      };
    }

    /** Actions for copying a given resource to another location. */
    public interface CopyActions {
      File createFileTestCopy(String resourcePath) throws IOException;
    }
  }

  /** Actions supported for Protobuf data files. */
  interface ProtoActions<P extends Message> {

    P loadJson(String jsonProtoFile);

    P loadText(String textProtoFile);

    List<P> loadAllTextFiles(List<String> textPbFiles);

    List<P> loadAllTextFiles(String... textPbFiles);

    List<P> loadAllJsonFiles(List<String> jsonPbFiles);

    List<P> loadAllJsonFiles(String jsonPbFile, String... jsonPbFiles);

    List<P> loadAllJsonFilesLike(String baseDir, String filePattern);
  }

  /**
   * Exception class to represent an unchecked exception when using {@link
   * com.google.cloud.solutions.satools.common.testing.TestResourceLoader}.
   *
   * <p>Using unchecked exception to simplify testing code.
   */
  final class ResourceLoadException extends RuntimeException {
    public ResourceLoadException(String fileName, Throwable cause) {
      super("Error reading test resource: " + fileName, cause);
    }
  }
}
