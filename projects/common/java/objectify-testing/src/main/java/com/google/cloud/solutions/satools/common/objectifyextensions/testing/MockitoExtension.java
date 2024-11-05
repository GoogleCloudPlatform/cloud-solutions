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

import org.junit.jupiter.api.extension.BeforeEachCallback;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.mockito.MockitoAnnotations;

/** Extension to Mockito framework to add context searching within the test instance. */
public class MockitoExtension implements BeforeEachCallback {
  @Override
  public void beforeEach(final ExtensionContext context) {
    final Object testInstance = context.getTestInstance().get();

    MockitoAnnotations.initMocks(testInstance);
  }
}
