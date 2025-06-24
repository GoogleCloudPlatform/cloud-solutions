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

import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component
@Profile("data-init")
public class DataInitializer implements CommandLineRunner {

  private static final Logger logger = LoggerFactory.getLogger(DataInitializer.class);

  @Autowired private ReviewRepository reviewRepository;

  @Value("${app.data.load:false}")
  private boolean shouldLoadData;

  @Override
  public void run(String... args) throws Exception {
    if (!shouldLoadData) {
      return;
    }

    logger.info("Starting review data initialization...");
    reviewRepository.deleteAll();

    List<Review> reviews =
        List.of(
            new Review(
                "9781492032649", "Data Architect", 5, "A must-read for any software engineer."),
            new Review("9781492032649", "Junior Dev", 5, "Challenging but incredibly insightful."),
            new Review(
                "9780321356680",
                "Senior Engineer",
                4,
                "Solid advice, though some examples are a bit dated."),
            new Review(
                "9780134685991",
                "Java Guru",
                5,
                "The definitive guide to writing better Java code."));

    reviewRepository.saveAll(reviews);
    logger.info("Populated {} reviews into PostgreSQL.", reviews.size());
  }
}
