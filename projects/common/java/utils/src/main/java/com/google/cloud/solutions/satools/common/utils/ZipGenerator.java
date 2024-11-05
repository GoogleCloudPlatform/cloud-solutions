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

import com.google.common.base.MoreObjects;
import com.google.common.collect.ImmutableList;
import com.google.common.hash.Hashing;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.function.Function;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Utility Class to provide in-memory file contents zipping capability. */
public class ZipGenerator {

  private final ImmutableList<ZipFileContent> files;

  public ZipGenerator(ImmutableList<ZipFileContent> files) {
    this.files = files;
  }

  public ZipGenerator(List<ZipFileContent> files) {
    this(ImmutableList.copyOf(files));
  }

  public static ZipGenerator of(ZipFileContent file) {
    return new ZipGenerator(ImmutableList.of(file));
  }

  public static ZipGenerator of(String fileName, byte[] content) {
    return of(ZipFileContent.of(fileName, content));
  }

  /**
   * Returns the bytes for zip file with the contents based on provided list of {@link
   * ZipFileContent}.
   */
  public byte[] makeZipFile() throws IOException {
    try (var zippedOutput = new ByteArrayOutputStream()) {
      makeZipFile(zippedOutput);
      return zippedOutput.toByteArray();
    }
  }

  /**
   * Writes the zipped output the provided {@link OutputStream}.
   *
   * <p>The method is automatically close the outputstream.
   *
   * @param outputStream the output stream to write th zip output of the provided {@link
   *     ZipFileContent}s.
   * @throws IOException when an issue in writing the ZipOutputstream to the provided outputstream
   */
  public void makeZipFile(OutputStream outputStream) throws IOException {

    try (var zipStream = new ZipOutputStream(outputStream)) {

      var zipEntryMaker = new ZipEntryMaker();

      files.stream()
          .sorted(Comparator.comparing(ZipFileContent::fileName))
          .map(zipEntryMaker::createAddEntryFn)
          .forEach(addFn -> addFn.apply(zipStream));

      zipStream.flush();
      zipStream.finish();
    }
  }

  /** Convenience Functional interface for building a ZIPEntry from a {@link ZipFileContent}. */
  private static class ZipEntryMaker {

    Function<ZipOutputStream, Void> createAddEntryFn(ZipFileContent zipFileContent) {
      return zipOutputStream -> {
        try {
          zipOutputStream.putNextEntry(new ZipEntry(zipFileContent.fileName()));
          zipOutputStream.write(zipFileContent.contents());
          zipOutputStream.closeEntry();
        } catch (IOException ioException) {
          throw new RuntimeException(
              String.format("error creating entry: %s", zipFileContent.fileName()), ioException);
        }
        return null;
      };
    }
  }

  /** Simple data structure to capture contents of a Zip File and its name. */
  public record ZipFileContent(String fileName, byte[] contents, boolean textContents) {

    public static ZipFileContent text(String fileName, byte[] contents) {
      return new ZipFileContent(fileName, contents, true);
    }

    public static ZipFileContent of(String fileName, byte[] contents) {
      return new ZipFileContent(fileName, contents, false);
    }

    /**
     * Custom {@code hashCode} and {@code equals} implementation required as the default
     * implementation does not perform deep comparison.
     */
    @Override
    public boolean equals(Object o) {
      if (this == o) {
        return true;
      }
      if (o == null || getClass() != o.getClass()) {
        return false;
      }

      ZipFileContent that = (ZipFileContent) o;
      return Objects.equals(fileName, that.fileName) && Objects.deepEquals(contents, that.contents);
    }

    @Override
    public int hashCode() {
      return Objects.hash(fileName, Arrays.hashCode(contents));
    }

    @Override
    public String toString() {
      return MoreObjects.toStringHelper(this)
          .add("fileName", fileName)
          .add("textContents", textContents)
          .add(
              "contents",
              (textContents)
                  ? new String(contents, StandardCharsets.UTF_8)
                  : Hashing.sha256().hashBytes(contents).toString())
          .toString();
    }
  }
}
