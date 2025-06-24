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

package com.example.reviewservice; // Corrected package name

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.*;
import java.time.Instant;

@Entity
@Table(name = "reviews")
public class Review {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  private Long id;

  @NotNull
  @Size(min = 10, max = 13)
  @Pattern(regexp = "^[0-9-]*$", message = "ISBN must contain only numbers and dashes")
  private String bookIsbn;

  @NotNull
  @Size(min = 1, max = 100)
  @Pattern(regexp = "^[\\w\\s'-]*$", message = "Reviewer name contains invalid characters")
  private String reviewerName;

  @Min(1)
  @Max(5)
  private int rating; // e.g., 1 to 5

  @NotNull
  @Size(min = 1, max = 5000)
  @Pattern(regexp = "^[\\w\\s.,'\"!?-]*$", message = "Review text contains invalid characters")
  private String reviewText;

  private Instant reviewDate;

  public Review() {}

  public Review(String bookIsbn, String reviewerName, int rating, String reviewText) {
    this.bookIsbn = bookIsbn;
    this.reviewerName = reviewerName;
    this.rating = rating;
    this.reviewText = reviewText;
    this.reviewDate = Instant.now();
  }

  // Getters and Setters...
  public Long getId() {
    return id;
  }

  public void setId(Long id) {
    this.id = id;
  }

  public String getBookIsbn() {
    return bookIsbn;
  }

  public void setBookIsbn(String bookIsbn) {
    this.bookIsbn = bookIsbn;
  }

  public String getReviewerName() {
    return reviewerName;
  }

  public void setReviewerName(String reviewerName) {
    this.reviewerName = reviewerName;
  }

  public int getRating() {
    return rating;
  }

  public void setRating(int rating) {
    this.rating = rating;
  }

  public String getReviewText() {
    return reviewText;
  }

  public void setReviewText(String reviewText) {
    this.reviewText = reviewText;
  }

  public Instant getReviewDate() {
    return reviewDate;
  }

  public void setReviewDate(Instant reviewDate) {
    this.reviewDate = reviewDate;
  }
}
