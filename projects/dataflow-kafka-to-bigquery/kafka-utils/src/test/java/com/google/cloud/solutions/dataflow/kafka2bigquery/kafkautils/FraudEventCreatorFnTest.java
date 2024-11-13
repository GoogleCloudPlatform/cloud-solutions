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

package com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils;

import static com.google.common.truth.extensions.proto.ProtoTruth.assertThat;

import com.google.cloud.solutions.dataflow.protofn.FraudEventCreatorFnFactory;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import demo.fraud.FraudEventOuterClass.FraudEvent;
import java.io.IOException;
import org.junit.Test;

public final class FraudEventCreatorFnTest {

  @Test
  public void apply_generatesRandomEvent() throws IOException {

    var fnFactory = new FraudEventCreatorFnFactory.TestFraudEventCreatorFnFactory();

    assertThat(fnFactory.fixedFraudEventFn().apply(1L))
        .isEqualTo(
            TestResourceLoader.classPath()
                .forProto(FraudEvent.class)
                .loadText("fraud_event_random_seed_1_clock_1730472569L.txtpb"));
  }
}
