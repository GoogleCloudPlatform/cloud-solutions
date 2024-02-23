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
import com.google.cloud.dataflow.model.Order;
import com.google.cloud.dataflow.model.OrderMutation;
import org.apache.beam.sdk.transforms.SerializableFunction;

class OrderMutationToTableRow implements SerializableFunction<OrderMutation, TableRow> {

  private static final long serialVersionUID = 1L;

  @Override
  public TableRow apply(OrderMutation input) {
    Order order = input.getOrder();
    TableRow result = new TableRow();
    result.set("order_id", order.getId());
    result.set("status", order.getStatus());
    result.set("description", order.getDescription());

    return result;
  }
}
