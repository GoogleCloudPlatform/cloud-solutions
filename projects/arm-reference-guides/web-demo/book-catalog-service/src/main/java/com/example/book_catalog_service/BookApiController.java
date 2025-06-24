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

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/books")
public class BookApiController {

  @Autowired private BookRepository bookRepository;

  @Autowired private RedisTemplate<String, String> redisTemplate;

  @Autowired private ObjectMapper objectMapper;

  @Autowired private SystemService systemService;

  private static final String POPULAR_BOOKS_KEY = "popular_books";

  @GetMapping("/arch")
  public String getArch() {
    return systemService.getCpuArch();
  }

  /**
   * MODIFIED: Added @PageableDefault to sort by title ascending if no other sort parameter is
   * provided in the URL.
   */
  @GetMapping
  public Page<Book> getPaginatedBooks(
      @PageableDefault(sort = "title", direction = Sort.Direction.ASC) Pageable pageable) {
    return bookRepository.findAll(pageable);
  }

  /** MODIFIED: Added an explicit sort by title to the full list query. */
  @GetMapping("/all")
  public List<Book> getAllBooks() {
    return bookRepository.findAll(Sort.by(Sort.Direction.ASC, "title"));
  }

  @GetMapping("/popular")
  public List<Book> getPopularBooks() {
    List<String> randomIsbnSubset = redisTemplate.opsForZSet().randomMembers(POPULAR_BOOKS_KEY, 10);
    if (randomIsbnSubset == null || randomIsbnSubset.isEmpty()) {
      return Collections.emptyList();
    }
    return bookRepository.findAllById(randomIsbnSubset);
  }

  @PostMapping("/popular/{isbn}")
  public ResponseEntity<Void> addPopularBook(@PathVariable String isbn) {
    if (!bookRepository.existsById(isbn)) {
      return ResponseEntity.notFound().build();
    }
    redisTemplate.opsForZSet().incrementScore(POPULAR_BOOKS_KEY, isbn, 1.0);
    return new ResponseEntity<>(HttpStatus.CREATED);
  }

  @PostMapping("/popular/batch")
  public ResponseEntity<String> addPopularBooksInBatch(@RequestBody List<String> isbns) {
    List<String> existingIsbns =
        isbns.stream().filter(isbn -> bookRepository.existsById(isbn)).collect(Collectors.toList());
    if (!existingIsbns.isEmpty()) {
      existingIsbns.forEach(
          isbn -> redisTemplate.opsForZSet().incrementScore(POPULAR_BOOKS_KEY, isbn, 1.0));
    }
    return ResponseEntity.status(HttpStatus.CREATED)
        .body(existingIsbns.size() + " valid ISBNs had their popularity score incremented.");
  }

  @DeleteMapping("/popular/{isbn}")
  public ResponseEntity<Void> removePopularBook(@PathVariable String isbn) {
    redisTemplate.opsForZSet().remove(POPULAR_BOOKS_KEY, isbn);
    return new ResponseEntity<>(HttpStatus.NO_CONTENT);
  }

  @GetMapping("/{isbn}")
  public ResponseEntity<Book> getBookByIsbn(@PathVariable String isbn) {
    return bookRepository
        .findById(isbn)
        .map(ResponseEntity::ok)
        .orElse(ResponseEntity.notFound().build());
  }

  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public Book addBook(@Valid @RequestBody Book book) {
    return bookRepository.save(book);
  }

  @PostMapping("/batch")
  public ResponseEntity<String> addBooksInBatch(@Valid @RequestBody List<Book> books) {
    bookRepository.saveAll(books);
    return ResponseEntity.status(HttpStatus.CREATED)
        .body(books.size() + " books were added successfully.");
  }

  @DeleteMapping("/{isbn}")
  public ResponseEntity<Void> deleteBook(@PathVariable String isbn) {
    if (!bookRepository.existsById(isbn)) {
      return new ResponseEntity<>(HttpStatus.NOT_FOUND);
    }
    removePopularBook(isbn);
    bookRepository.deleteById(isbn);
    return new ResponseEntity<>(HttpStatus.NO_CONTENT);
  }
}
