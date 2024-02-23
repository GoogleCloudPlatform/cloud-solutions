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

package com.google.cloud.dataflow.model;

import com.google.cloud.dataflow.model.Order.Status;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.List;
import java.util.Objects;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.CoderException;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.coders.VarLongCoder;
import org.apache.beam.sdk.io.gcp.bigquery.RowMutationInformation;
import org.apache.beam.sdk.io.gcp.bigquery.RowMutationInformation.MutationType;
import org.checkerframework.checker.initialization.qual.Initialized;
import org.checkerframework.checker.nullness.qual.NonNull;
import org.checkerframework.checker.nullness.qual.UnknownKeyFor;

/**
 * Order mutation. Contains both order attributes and information about whether it's an UPSERT or
 * DELETE
 */
public class OrderMutation {

  /** Coder for OrderMutation. */
  public static class OrderMutationCoder extends Coder<OrderMutation> {
    private static final long serialVersionUID = 1L;

    @Override
    public void encode(
        OrderMutation value, @UnknownKeyFor @NonNull @Initialized OutputStream outStream)
        throws @UnknownKeyFor @NonNull @Initialized CoderException,
            @UnknownKeyFor @NonNull @Initialized IOException {
      Order order = value.getOrder();
      VarLongCoder.of().encode(order.getId(), outStream);
      StringUtf8Coder.of().encode(order.getStatus().name(), outStream);
      StringUtf8Coder.of().encode(order.getDescription(), outStream);

      RowMutationInformation rowMutationInformation = value.getMutationInformation();
      VarLongCoder.of().encode(rowMutationInformation.getSequenceNumber(), outStream);
      StringUtf8Coder.of().encode(rowMutationInformation.getMutationType().name(), outStream);
    }

    @Override
    public OrderMutation decode(@UnknownKeyFor @NonNull @Initialized InputStream inStream)
        throws @UnknownKeyFor @NonNull @Initialized CoderException,
            @UnknownKeyFor @NonNull @Initialized IOException {
      Order order = new Order();
      order.setId(VarLongCoder.of().decode(inStream));
      order.setStatus(Status.valueOf(StringUtf8Coder.of().decode(inStream)));
      order.setDescription(StringUtf8Coder.of().decode(inStream));

      long sequenceNumber = VarLongCoder.of().decode(inStream);
      MutationType mutationType = MutationType.valueOf(StringUtf8Coder.of().decode(inStream));
      RowMutationInformation rowMutationInformation =
          RowMutationInformation.of(mutationType, sequenceNumber);

      OrderMutation result = new OrderMutation();
      result.setMutationInformation(rowMutationInformation);
      result.setOrder(order);

      return result;
    }

    @Override
    public @UnknownKeyFor @NonNull @Initialized List<
            ? extends
                @UnknownKeyFor @NonNull @Initialized Coder<@UnknownKeyFor @NonNull @Initialized ?>>
        getCoderArguments() {
      return null;
    }

    @Override
    public void verifyDeterministic()
        throws @UnknownKeyFor @NonNull @Initialized NonDeterministicException {}
  }

  private RowMutationInformation mutationInformation;
  private Order order;

  public RowMutationInformation getMutationInformation() {
    return mutationInformation;
  }

  public void setMutationInformation(RowMutationInformation mutationInformation) {
    this.mutationInformation = mutationInformation;
  }

  public Order getOrder() {
    return order;
  }

  public void setOrder(Order order) {
    this.order = order;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) {
      return true;
    }
    if (!(o instanceof OrderMutation)) {
      return false;
    }
    OrderMutation that = (OrderMutation) o;
    return mutationInformation.equals(that.mutationInformation) && order.equals(that.order);
  }

  @Override
  public int hashCode() {
    return Objects.hash(mutationInformation, order);
  }

  @Override
  public String toString() {
    return "OrderMutation{"
        + "mutationInformation="
        + mutationInformation
        + ", order="
        + order
        + '}';
  }
}
