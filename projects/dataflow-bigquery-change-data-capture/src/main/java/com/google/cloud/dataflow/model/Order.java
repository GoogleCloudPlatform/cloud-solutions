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

import java.util.Objects;

/** Demo class to simulate a generic order. */
public class Order {

  /** Order status. */
  public enum Status {
    NEW,
    SCHEDULED,
    PROCESSED,
    DELETED
  }

  private long id;
  private Status status;
  private String description;

  public Order() {}

  /** Constructor to create a fully instantiated order. */
  public Order(long id, Status status, String description) {
    this.id = id;
    this.description = description;
    this.status = status;
  }

  public long getId() {
    return id;
  }

  public void setId(long id) {
    this.id = id;
  }

  public Status getStatus() {
    return status;
  }

  public void setStatus(Status status) {
    this.status = status;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) {
      return true;
    }
    if (!(o instanceof Order)) {
      return false;
    }
    Order order = (Order) o;
    return id == order.id
        && Objects.equals(status, order.status)
        && Objects.equals(description, order.description);
  }

  @Override
  public int hashCode() {
    return Objects.hash(id, status, description);
  }

  @Override
  public String toString() {
    return "Order{"
        + "id="
        + id
        + ", status="
        + status
        + ", description='"
        + description
        + '\''
        + '}';
  }
}
