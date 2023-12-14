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

package com.google.cloud.solutions.satools.perfbenchmark;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobStatus;
import com.googlecode.objectify.Objectify;
import com.googlecode.objectify.ObjectifyFactory;
import com.googlecode.objectify.ObjectifyService;

/** Global class to register Objectify Entities and provide static methods to access Objectify. */
public final class DatastoreService {

  static {
    registerEntities();
  }

  public static void registerEntities() {
    ObjectifyService.register(BenchmarkJobEntity.class);
    ObjectifyService.register(BenchmarkJobStatus.class);
  }

  /**
   * Loads any of the registered entity Objects using their id.
   *
   * @param entityType class of the entity to load
   * @param id the Id of the entity to load
   * @param <T> the Generic class identifier for entity classes
   * @return the Object read from the Datastore or null if not found
   */
  public static <T> T loadEntity(final Class<T> entityType, final Long id) {
    checkNotNull(entityType, "entity type is null");
    checkNotNull(id, "entity Id can't be null");

    return ofy().load().type(entityType).id(id).now();
  }

  public static <T> T loadEntitySafe(final Class<T> entityType, final long id) {
    return ofy().load().type(entityType).id(id).safe();
  }

  /**
   * Helper method to allow using Objectify Service in static imports as per the Objectify <a
   * href="https://github.com/objectify/objectify/wiki/Setup">best practices</a>.
   *
   * @return Objectify instance in the given context
   */
  public static Objectify ofy() {
    return ObjectifyService.ofy();
  }

  /**
   * Helper method to provide ObjectifyFactory for Entity Registration.
   *
   * @return Factory to register Entity classes
   */
  private static ObjectifyFactory factory() {
    return ObjectifyService.factory();
  }

  private DatastoreService() {}
}
