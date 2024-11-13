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

package com.google.cloud.solutions.dataflow.protofn;

import com.google.protobuf.Message;
import demo.fraud.EvolvedFraudEventOuterClass.EvolvedFraudEvent;
import demo.fraud.FraudEventOuterClass.FraudEvent;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.Iterator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Random;
import java.util.function.Function;

public interface FraudEventCreatorFnFactory {

  Clock FIXED_TEST_CLOCK = Clock.fixed(Instant.ofEpochMilli(1730472569L), ZoneId.of("UTC"));

  Function<Long, FraudEvent> fraudEventFn();

  Function<Long, FraudEvent> fixedFraudEventFn(Integer seed, Clock clock);

  Function<Long, EvolvedFraudEvent> evolvedEventFn();

  Function<Long, EvolvedFraudEvent> fixedEvolvedFraudEventFn(Integer seed, Clock clock);

  default Function<Long, FraudEvent> fixedFraudEventFn() {
    return fixedFraudEventFn(1, FIXED_TEST_CLOCK);
  }

  default Function<Long, EvolvedFraudEvent> fixedEvolvedEventFn() {
    return fixedEvolvedFraudEventFn(1, FIXED_TEST_CLOCK);
  }

  default <T extends Message> Function<Long, T> fixedQuantityEventFn(
      int quantity, Function<Long, T> eventGenFn) {
    return new Function<>() {
      long count = 0;

      @Override
      public T apply(Long longId) {
        if (count < quantity) {
          return eventGenFn.apply(count++);
        }
        throw new NoSuchElementException();
      }
    };
  }

  default <T extends Message> Function<Long, T> fixedListEventsFn(List<T> records) {
    return new Function<>() {
      private Iterator<T> iterator = records.iterator();

      @Override
      public T apply(Long input) {
        return iterator.next();
      }
    };
  }

  class TestFraudEventCreatorFnFactory implements FraudEventCreatorFnFactory {

    @Override
    public FraudEventCreatorFn fixedFraudEventFn(Integer seed, Clock clock) {
      return new FraudEventCreatorFn(new Random(seed), clock);
    }

    @Override
    public Function<Long, FraudEvent> fraudEventFn() {
      return new FraudEventCreatorFn(new Random(), Clock.systemUTC());
    }

    @Override
    public Function<Long, EvolvedFraudEvent> evolvedEventFn() {
      return new EvolvedFraudEventCreatorFn(new Random(), Clock.systemUTC());
    }

    @Override
    public Function<Long, EvolvedFraudEvent> fixedEvolvedFraudEventFn(Integer seed, Clock clock) {
      return new EvolvedFraudEventCreatorFn(new Random(seed), clock);
    }
  }
}
