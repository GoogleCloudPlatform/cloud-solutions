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

package com.google.cloud.solutions.delgcsbqfn;

import com.google.api.gax.rpc.HeaderProvider;
import com.google.common.collect.ImmutableMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** Provides User-Agent based tracking for solution usage. */
@Component
public class UserAgentHeaderProvider implements HeaderProvider {
  private final ImmutableMap<String, String> userAgent;

  public UserAgentHeaderProvider(@Value("${bulkgcsdelfn.version}") String version) {
    this.userAgent =
        ImmutableMap.of("user-agent", "cloud-solutions/tool-bulk-delete-gcs-function-v" + version);
  }

  @Override
  public Map<String, String> getHeaders() {
    return userAgent;
  }
}
