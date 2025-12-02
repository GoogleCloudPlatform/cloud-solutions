/**
 * Copyright 2025 Google LLC
 *
 * <p>Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file
 * except in compliance with the License. You may obtain a copy of the License at
 *
 * <p>https://www.apache.org/licenses/LICENSE-2.0
 *
 * <p>Unless required by applicable law or agreed to in writing, software distributed under the
 * License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing permissions and
 * limitations under the License
 */
package org.google.demo;

import io.quarkus.hibernate.orm.panache.PanacheEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import java.math.BigDecimal;
import java.net.URL;
import java.time.LocalDateTime;
import java.util.List;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

/** Represents a menu item in the restaurant. */
@Entity
public class Menu extends PanacheEntity {

  @Column(name = "item_name")
  public String itemName;

  @Column(name = "item_price")
  public BigDecimal itemPrice;

  @Column(name = "default_spice_level", columnDefinition = "integer default 0")
  public int spiceLevel;

  @Column(name = "tag_line")
  public String tagLine; // "sweets delight", "super spicy"

  @Column(name = "item_image_url")
  public URL itemImageUrl;

  @Column(name = "item_thumbnail_url")
  public URL itemThumbnailUrl;

  @Column(name = "item_status")
  public Status status;

  @CreationTimestamp
  @Column(name = "creation_timestamp")
  public LocalDateTime createDateTime;

  @UpdateTimestamp
  @Column(name = "update_timestamp")
  public LocalDateTime updateDateTime;

  /**
   * Finds all menu items with the status 'Ready'.
   *
   * @return a list of ready menu items
   */
  public static List<Menu> findReady() {
    return list("status", Status.Ready);
  }

  /**
   * Finds all menu items with the status 'Failed'.
   *
   * @return a list of failed menu items
   */
  public static List<Menu> findFailed() {
    return list("status", Status.Failed);
  }

  /**
   * Finds all menu items with the status 'Processing'.
   *
   * @return a list of processing menu items
   */
  public static List<Menu> findProcessing() {
    return list("status", Status.Processing);
  }
}
