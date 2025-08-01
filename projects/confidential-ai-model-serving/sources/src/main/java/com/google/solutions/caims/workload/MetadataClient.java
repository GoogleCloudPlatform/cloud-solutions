//
// Copyright 2025 Google LLC
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//

package com.google.solutions.caims.workload;

import com.google.api.client.http.ByteArrayContent;
import com.google.api.client.http.GenericUrl;
import com.google.api.client.http.HttpRequestFactory;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.JsonObjectParser;
import com.google.api.client.json.gson.GsonFactory;
import com.google.api.client.util.GenericData;
import com.google.auth.oauth2.ComputeEngineCredentials;
import com.google.common.base.Preconditions;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.jetbrains.annotations.NotNull;

/** Helper class for interacting with the Compute Engine metadata server. */
public class MetadataClient {
  private static final HttpRequestFactory HTTP_FACTORY =
      new NetHttpTransport().createRequestFactory();

  /** Publish a guest attribute for the current VM. */
  public void setGuestAttribute(
      @NotNull String namespace, @NotNull String name, @NotNull String value) throws IOException {
    Preconditions.checkArgument(!namespace.contains("/"), "Namespace must not contain slashes");
    Preconditions.checkArgument(!name.contains("/"), "Name must not contain slashes");

    var url =
        new GenericUrl(
            String.format(
                "%s/computeMetadata/v1/instance/guest-attributes/%s/%s",
                ComputeEngineCredentials.getMetadataServerUrl(), namespace, name));

    var request =
        HTTP_FACTORY
            .buildPutRequest(
                url, new ByteArrayContent("text/plain", value.getBytes(StandardCharsets.UTF_8)))
            .setParser(new JsonObjectParser(GsonFactory.getDefaultInstance()))
            .setThrowExceptionOnExecuteError(true);

    request.getHeaders().set("Metadata-Flavor", "Google");

    try {
      request.execute();
    } catch (Exception exception) {
      throw new IOException("Setting guest attribute failed", exception);
    }
  }

  /** Get project metadata for the current VM. */
  public @NotNull GenericData getProjectMetadata() throws IOException {
    return getMetadata("/computeMetadata/v1/project/");
  }

  /** Get instance metadata for the current VM. */
  public @NotNull GenericData getInstanceMetadata() throws IOException {
    return getMetadata("/computeMetadata/v1/instance/");
  }

  private @NotNull GenericData getMetadata(@NotNull String path) throws IOException {
    var url =
        new GenericUrl(ComputeEngineCredentials.getMetadataServerUrl() + path + "?recursive=true");

    var request =
        HTTP_FACTORY
            .buildGetRequest(url)
            .setParser(new JsonObjectParser(GsonFactory.getDefaultInstance()))
            .setThrowExceptionOnExecuteError(true);

    request.getHeaders().set("Metadata-Flavor", "Google");

    try {
      return request.execute().parseAs(GenericData.class);
    } catch (Exception exception) {
      throw new IOException(
          "Cannot find the metadata server, possibly because code is not running on Google Cloud",
          exception);
    }
  }
}
