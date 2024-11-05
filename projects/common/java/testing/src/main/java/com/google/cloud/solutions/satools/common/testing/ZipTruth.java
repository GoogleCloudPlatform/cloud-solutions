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

import com.google.cloud.solutions.satools.common.utils.ZipGenerator.ZipFileContent;
import com.google.common.truth.IterableSubject;
import com.google.common.truth.Truth;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Provides Google Truth like assert statement to compare contents of a zip archive. */
public class ZipTruth {

  private final boolean textContent;

  private ZipTruth(boolean textContent) {
    this.textContent = textContent;
  }

  public static ZipTruth forText() {
    return new ZipTruth(true);
  }

  public static ZipTruth forBinary() {
    return new ZipTruth(false);
  }

  public IterableSubject assertThat(File testZipFile) throws IOException {
    return assertThat(new FileInputStream(testZipFile));
  }

  public IterableSubject assertThat(byte[] zipBytes) throws IOException {
    return assertThat(new ByteArrayInputStream(zipBytes));
  }

  /**
   * Google Truth style assertThat function to assert comparison of zip contents with
   * ZipFileContents.
   */
  public IterableSubject assertThat(InputStream testInputStream) throws IOException {

    try (var testZipStream = new ZipInputStream(testInputStream)) {
      var entries = new ArrayList<ZipFileContent>();
      ZipEntry entry;
      while ((entry = testZipStream.getNextEntry()) != null) {
        entries.add(new ZipFileContent(entry.getName(), testZipStream.readAllBytes(), textContent));
      }
      return Truth.assertThat(entries);
    }
  }
}
