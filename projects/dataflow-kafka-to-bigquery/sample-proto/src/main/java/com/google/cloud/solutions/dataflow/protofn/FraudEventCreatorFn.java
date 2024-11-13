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

import static com.google.common.base.Preconditions.checkNotNull;

import demo.fraud.FraudEventOuterClass.FraudEvent;
import demo.fraud.FraudEventOuterClass.FraudEvent.Destination;
import demo.fraud.FraudEventOuterClass.FraudEvent.Original;
import java.time.Clock;
import java.util.Random;
import java.util.function.Function;

/** Sample FraudEventCreator that generates random events. */
public final class FraudEventCreatorFn implements Function<Long, FraudEvent> {

  private final Random random;
  private final Clock clock;

  public FraudEventCreatorFn(Random random, Clock clock) {
    this.random = checkNotNull(random);
    this.clock = checkNotNull(clock);
  }

  @Override
  public FraudEvent apply(Long randomLong) {
    return FraudEvent.newBuilder()
        .setTstamp(clock.millis())
        .setTType("millis")
        .setAmount(random.nextFloat(100, 10000))
        .setOriginal(
            Original.newBuilder()
                .setNameOriginal("A" + randomLong)
                .setOldBalanceOriginal(random.nextFloat(100, 10000))
                .setNewBalanceOriginal(random.nextFloat(100, 10000)))
        .setDestination(
            Destination.newBuilder()
                .setNameDestination("B" + randomLong)
                .setOldBalanceDestination(random.nextFloat(100, 10000))
                .setNewBalanceDestination(random.nextFloat(100, 10000)))
        .setIsFraud(random.nextInt(0, 2)) // upper bound is exclusive
        .setIsFlaggedFraud(random.nextInt(0, 2)) // upper bound is exclusive
        .setGeoLat(random.nextFloat(-180, 180))
        .setGeoLong(random.nextFloat(-180, 180))
        .build();
  }
}
