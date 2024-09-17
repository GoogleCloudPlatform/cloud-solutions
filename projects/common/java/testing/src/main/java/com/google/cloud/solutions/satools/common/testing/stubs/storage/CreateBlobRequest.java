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

package com.google.cloud.solutions.satools.common.testing.stubs.storage;

import com.google.cloud.storage.BlobInfo;
import com.google.cloud.storage.Storage;
import com.google.common.base.MoreObjects;
import java.util.Arrays;
import java.util.Base64;
import java.util.Objects;

/** Record class to represent creating a new blob on Cloud Storage. */
public record CreateBlobRequest(
    BlobInfo blobInfo, byte[] content, Storage.BlobTargetOption... options) {

  @Override
  public String toString() {
    return MoreObjects.toStringHelper(this)
        .add("blobInfo", blobInfo)
        .add("content", content != null ? Base64.getEncoder().encodeToString(content) : null)
        .add("options", options)
        .toString();
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) {
      return true;
    }

    return (o instanceof CreateBlobRequest that)
        && Objects.deepEquals(blobInfo, that.blobInfo)
        && Arrays.equals(content, that.content)
        && Arrays.equals(options, that.options);
  }

  @Override
  public int hashCode() {
    return Objects.hash(blobInfo, Arrays.hashCode(content), Arrays.hashCode(options));
  }
}
