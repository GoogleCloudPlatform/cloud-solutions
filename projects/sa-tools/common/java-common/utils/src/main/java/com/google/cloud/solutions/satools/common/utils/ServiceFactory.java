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

/**
 * Generic interface to describe an arbitrary API Client factory.
 *
 * @param <T> the type of client that the factory will create.
 * @param <InitT> the type of initialization parameter the factory will need to create the client.
 */
public interface ServiceFactory<T, InitT> {

  /** Returns a default client. */
  T create() throws Exception;

  /**
   * Returns a client based on the provided initialization parameters.
   *
   * <p>The initialization parameters can be any user-provided headers etc.
   *
   * @param settings the initialization parameter
   * @return the client created by using provided settings.
   * @throws Exception when encounters any exception in creating the service object.
   */
  T create(InitT settings) throws Exception;
}
