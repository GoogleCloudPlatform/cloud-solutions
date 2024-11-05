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

package com.google.cloud.solutions.satools.common.objectifyextensions.testing;

import com.google.common.flogger.GoogleLogger;
import java.net.InetSocketAddress;
import net.spy.memcached.MemcachedClient;
import org.junit.jupiter.api.extension.BeforeAllCallback;
import org.junit.jupiter.api.extension.BeforeEachCallback;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.extension.ExtensionContext.Namespace;

/** Resets a local memcached client on every test run. */
public class LocalMemcacheExtension implements BeforeAllCallback, BeforeEachCallback {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  @Override
  public void beforeAll(final ExtensionContext context) throws Exception {
    if (getClient(context) == null) {
      logger.atInfo().log("Creating new MemcachedClient");

      final MemcachedClient client = new MemcachedClient(new InetSocketAddress("localhost", 11211));
      context.getRoot().getStore(Namespace.GLOBAL).put(MemcachedClient.class, client);
    }
  }

  @Override
  public void beforeEach(final ExtensionContext context) {
    final MemcachedClient client = getClient(context);
    client.flush();
  }

  /** Get the helper created in beforeAll; it should be global so there will one per test run. */
  public static MemcachedClient getClient(final ExtensionContext context) {
    return context
        .getRoot()
        .getStore(Namespace.GLOBAL)
        .get(MemcachedClient.class, MemcachedClient.class);
  }
}
