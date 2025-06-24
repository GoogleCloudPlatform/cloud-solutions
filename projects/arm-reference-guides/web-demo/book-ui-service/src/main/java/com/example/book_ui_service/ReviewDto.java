/*
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.example.book_ui_service;

import java.time.Instant;

// This record is used to serialize/deserialize review data when communicating with the
// review-service.
public record ReviewDto(
    Long id,
    String bookIsbn,
    String reviewerName,
    int rating,
    String reviewText,
    Instant reviewDate) {
  // Constructor to help create a new DTO for the 'Add Review' form binding
  public ReviewDto(String bookIsbn) {
    this(null, bookIsbn, null, 5, null, null);
  }
}
