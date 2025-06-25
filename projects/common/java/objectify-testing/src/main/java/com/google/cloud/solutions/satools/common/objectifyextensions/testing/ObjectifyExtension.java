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

import com.google.cloud.datastore.Datastore;
import com.google.cloud.datastore.testing.LocalDatastoreHelper;
import com.google.common.base.Preconditions;
import com.googlecode.objectify.ObjectifyFactory;
import com.googlecode.objectify.ObjectifyService;
import com.googlecode.objectify.util.Closeable;
import org.junit.jupiter.api.extension.AfterEachCallback;
import org.junit.jupiter.api.extension.BeforeEachCallback;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.extension.ExtensionContext.Namespace;

/** Sets up and tears down the GAE local unit test harness environment. */
public class ObjectifyExtension implements BeforeEachCallback, AfterEachCallback {

  private static final Namespace NAMESPACE = Namespace.create(ObjectifyExtension.class);

  @Override
  public void beforeEach(final ExtensionContext context) throws Exception {
    final LocalDatastoreHelper helper = LocalDatastoreExtension.getHelper(context);
    Preconditions.checkNotNull(
        helper, "This extension depends on " + LocalDatastoreExtension.class.getSimpleName());

    final Datastore datastore = helper.getOptions().getService();

    ObjectifyService.init(new ObjectifyFactory(datastore));

    final Closeable rootService = ObjectifyService.begin();

    context.getStore(NAMESPACE).put(Closeable.class, rootService);
  }

  @Override
  public void afterEach(final ExtensionContext context) {
    final Closeable rootService = context.getStore(NAMESPACE).get(Closeable.class, Closeable.class);

    rootService.close();
  }
}
