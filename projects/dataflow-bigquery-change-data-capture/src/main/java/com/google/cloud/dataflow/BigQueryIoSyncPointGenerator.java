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

package com.google.cloud.dataflow;

import com.google.api.services.bigquery.model.TableRow;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryStorageApiInsertError;
import org.apache.beam.sdk.io.gcp.bigquery.WriteResult;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.PeriodicImpulse;
import org.apache.beam.sdk.transforms.Sample;
import org.apache.beam.sdk.transforms.windowing.AfterProcessingTime;
import org.apache.beam.sdk.transforms.windowing.BoundedWindow;
import org.apache.beam.sdk.transforms.windowing.FixedWindows;
import org.apache.beam.sdk.transforms.windowing.GlobalWindows;
import org.apache.beam.sdk.transforms.windowing.Repeatedly;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollection.IsBounded;
import org.apache.beam.sdk.values.PCollectionList;
import org.joda.time.Duration;
import org.joda.time.Instant;

/** Class which processes the BigQueryIO's WriteResult to produce sync points. */
public class BigQueryIoSyncPointGenerator {

  /**
   * Main method used to create a PCollection of sync points.
   *
   * @param bigQueryWriteResult Result of the BigQueryIO processing
   * @param frequency Frequency of the sync points
   * @param maxLatency Maximum latency to wait
   * @param heartbeatStartTime Start time for the heartbeats. Normally set to the current time.
   * @return PCollection of sync points
   */
  public static PCollection<Instant> generate(
      WriteResult bigQueryWriteResult,
      Duration frequency,
      Duration maxLatency,
      Instant heartbeatStartTime) {
    PCollection<TableRow> successfulWrites = bigQueryWriteResult.getSuccessfulStorageApiInserts();
    PCollection<BigQueryStorageApiInsertError> failedWrites =
        bigQueryWriteResult.getFailedStorageApiInserts();

    PCollectionList<Instant> pcollectionList =
        PCollectionList.of(
                successfulWrites.apply("Successful to Timestamp", ParDo.of(new ExtractTimestamp())))
            .and(failedWrites.apply("Failed to Timestamp", ParDo.of(new ExtractTimestamp())));
    return pcollectionList.apply(
        "Sync Points", new BigQueryIoSyncPointTransform(heartbeatStartTime, frequency, maxLatency));
  }

  static class BigQueryIoSyncPointTransform
      extends PTransform<PCollectionList<Instant>, PCollection<Instant>> {

    private static final long serialVersionUID = 1;

    private final Instant heartbeatStartTime;
    private final Duration frequency;
    private final Duration maxLatency;

    BigQueryIoSyncPointTransform(
        Instant heartbeatStartTime, Duration frequency, Duration maxLatency) {
      this.heartbeatStartTime = heartbeatStartTime;
      this.frequency = frequency;
      this.maxLatency = maxLatency;
    }

    @Override
    public PCollection<Instant> expand(PCollectionList<Instant> input) {
      PCollectionList<Instant> timestampPcollections = input;
      if (input.get(0).isBounded() == IsBounded.UNBOUNDED) {
        PCollection<Instant> heartBeats =
            input
                .getPipeline()
                .apply(
                    "Sync Detection Heartbeat",
                    PeriodicImpulse.create().withInterval(frequency).startAt(heartbeatStartTime));
        timestampPcollections = timestampPcollections.and(heartBeats);
      }

      return timestampPcollections
          .apply(Flatten.pCollections())
          .apply(
              "Into FixedWindow",
              Window.<Instant>into(FixedWindows.of(frequency)).withAllowedLateness(maxLatency))
          .apply("Combine", Sample.any(1))
          .apply("Get Window End", ParDo.of(new ExtractWindowEnd()))
          .apply(
              "Into GlobalWindow",
              Window.<Instant>into(new GlobalWindows())
                  .triggering(Repeatedly.forever(AfterProcessingTime.pastFirstElementInPane()))
                  .discardingFiredPanes());
    }
  }

  static class ExtractWindowEnd extends DoFn<Instant, Instant> {

    private static final long serialVersionUID = 1;

    @ProcessElement
    public void process(BoundedWindow window, OutputReceiver<Instant> outputReceiver) {
      outputReceiver.output(window.maxTimestamp());
    }
  }

  static class ExtractTimestamp extends DoFn<Object, Instant> {

    private static final long serialVersionUID = 1;

    @ProcessElement
    public void process(@Timestamp Instant timestamp, OutputReceiver<Instant> outputReceiver) {
      outputReceiver.output(timestamp);
    }
  }
}
