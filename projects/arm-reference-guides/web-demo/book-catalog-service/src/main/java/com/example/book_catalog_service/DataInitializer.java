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

package com.example.book_catalog_service;

import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

@Component
@Profile("!nodatabase & data-init")
public class DataInitializer implements CommandLineRunner {

  private static final Logger logger = LoggerFactory.getLogger(DataInitializer.class);

  @Autowired private BookRepository bookRepository;

  @Autowired private RedisTemplate<String, String> redisTemplate;

  @Value("${app.data.load:false}")
  private boolean shouldLoadData;

  @Override
  public void run(String... args) throws Exception {
    if (!shouldLoadData) {
      logger.info("Skipping data initialization because app.data.load is false.");
      return;
    }

    logger.info("Starting data initialization...");

    // 1. Populate PostgreSQL
    bookRepository.deleteAll(); // Clear existing data
    List<Book> books =
        List.of(
            new Book("9780134685991", "Effective Java", "Joshua Bloch", 2018, "Software"),
            new Book("9780321356680", "Clean Code", "Robert C. Martin", 2008, "Software"),
            new Book(
                "9780596007126", "Head First Design Patterns", "Eric Freeman", 2004, "Software"),
            new Book("9780735219090", "Atomic Habits", "James Clear", 2018, "Self-Help"),
            new Book(
                "9781492032649",
                "Designing Data-Intensive Applications",
                "Martin Kleppmann",
                2017,
                "Databases"),
            new Book(
                "9780262033848",
                "Introduction to Algorithms",
                "Thomas H. Cormen",
                2009,
                "Computer Science"));
    bookRepository.saveAll(books);
    logger.info("Populated {} books into PostgreSQL.", books.size());

    // 2. Populate Redis
    redisTemplate.delete("popular_books"); // Clear existing data
    // Use a score to represent "popularity". Higher score is more popular.
    redisTemplate
        .opsForZSet()
        .add("popular_books", "9781492032649", 100); // Designing Data-Intensive...
    redisTemplate.opsForZSet().add("popular_books", "9780321356680", 95); // Clean Code
    redisTemplate.opsForZSet().add("popular_books", "9780735219090", 90); // Atomic Habits
    logger.info("Populated popular books into Redis.");
  }
}
