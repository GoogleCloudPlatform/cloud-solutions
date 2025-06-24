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

package com.example.reviewservice;

import jakarta.transaction.Transactional;
import jakarta.validation.Valid;
import java.time.Instant;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/reviews")
public class ReviewController {

  @Autowired private ReviewRepository reviewRepository;

  @Autowired private SystemService systemService;

  @GetMapping("/arch")
  public String getArch() {
    return systemService.getCpuArch();
  }

  @GetMapping("/{isbn}")
  public List<Review> getReviewsForBook(@PathVariable String isbn) {
    return reviewRepository.findByBookIsbn(isbn);
  }

  @PostMapping
  public ResponseEntity<Review> addReview(@Valid @RequestBody Review newReview) {
    newReview.setReviewDate(Instant.now());
    Review savedReview = reviewRepository.save(newReview);
    return new ResponseEntity<>(savedReview, HttpStatus.CREATED);
  }

  @PostMapping("/batch")
  public ResponseEntity<String> addReviewsInBatch(@Valid @RequestBody List<Review> reviews) {
    reviews.forEach(review -> review.setReviewDate(Instant.now()));
    reviewRepository.saveAll(reviews);
    return ResponseEntity.status(HttpStatus.CREATED)
        .body(reviews.size() + " reviews were added successfully.");
  }

  @DeleteMapping("/{id}")
  public ResponseEntity<Void> deleteReview(@PathVariable Long id) {
    if (!reviewRepository.existsById(id)) {
      return new ResponseEntity<>(HttpStatus.NOT_FOUND);
    }
    reviewRepository.deleteById(id);
    return new ResponseEntity<>(HttpStatus.NO_CONTENT);
  }

  @DeleteMapping("/cleanup-k6-tests")
  @Transactional
  public ResponseEntity<String> cleanupK6Reviews() {
    int deletedCount = reviewRepository.deleteK6TestReviews();
    return ResponseEntity.ok("Cleaned up " + deletedCount + " test reviews.");
  }
}
