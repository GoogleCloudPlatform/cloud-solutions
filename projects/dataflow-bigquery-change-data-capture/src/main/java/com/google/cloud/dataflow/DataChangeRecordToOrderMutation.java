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

import com.google.cloud.dataflow.model.Order;
import com.google.cloud.dataflow.model.Order.Status;
import com.google.cloud.dataflow.model.OrderMutation;
import org.apache.beam.sdk.io.gcp.bigquery.RowMutationInformation;
import org.apache.beam.sdk.io.gcp.bigquery.RowMutationInformation.MutationType;
import org.apache.beam.sdk.io.gcp.spanner.changestreams.model.DataChangeRecord;
import org.apache.beam.sdk.io.gcp.spanner.changestreams.model.Mod;
import org.apache.beam.sdk.io.gcp.spanner.changestreams.model.ModType;
import org.apache.beam.sdk.transforms.DoFn;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

class DataChangeRecordToOrderMutation extends DoFn<DataChangeRecord, OrderMutation> {
  private static final Logger LOG = LoggerFactory.getLogger(DataChangeRecordToOrderMutation.class);
  private static final long serialVersionUID = 1L;

  @ProcessElement
  public void process(
      @Element DataChangeRecord record, OutputReceiver<OrderMutation> outputReceiver) {

    RowMutationInformation mutationInformation =
        RowMutationInformation.of(
            record.getModType() == ModType.DELETE ? MutationType.DELETE : MutationType.UPSERT,
            record.getCommitTimestamp().getSeconds() * 1_000_000_000
                + record.getCommitTimestamp().getNanos());

    for (Mod mod : record.getMods()) {
      JSONObject keyJson = new JSONObject(mod.getKeysJson());
      JSONObject valueJson = new JSONObject(mod.getNewValuesJson());

      Order order = new Order();
      order.setId(keyJson.getInt("order_id"));

      switch (record.getModType()) {
        case DELETE:
          order.setStatus(Status.DELETED);
          order.setDescription("Deleted order");
          break;

        default:
          order.setStatus(Status.valueOf(valueJson.getString("status")));
          order.setDescription(valueJson.getString("description"));
          break;
      }

      OrderMutation result = new OrderMutation();
      result.setOrder(order);
      result.setMutationInformation(mutationInformation);

      // This log output is for demo purposes only. Don't use it in production pipelines.
      LOG.info("Mutation: " + result);

      outputReceiver.output(result);
    }
  }
}
