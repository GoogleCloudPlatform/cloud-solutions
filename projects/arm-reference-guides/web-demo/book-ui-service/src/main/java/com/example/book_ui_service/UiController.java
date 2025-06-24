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

import com.opencsv.CSVReader;
import com.opencsv.exceptions.CsvValidationException;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;
import org.springframework.web.util.UriComponentsBuilder;

@Controller
public class UiController {

  private static final Logger logger = LoggerFactory.getLogger(UiController.class);

  @Autowired private RestTemplate restTemplate;

  @Autowired private SystemService systemService;

  @Value("${app.services.catalog.url}")
  private String bookApiUrl;

  @Value("${app.services.review.url}")
  private String reviewApiUrl;

  @GetMapping("/")
  public String home(Model model) {
    model.addAttribute("message", "Welcome to the Book Review System!");
    model.addAttribute("cpuArch", systemService.getCpuArch());
    try {
      String catalogCpuArch = restTemplate.getForObject(bookApiUrl + "/arch", String.class);
      model.addAttribute("catalogCpuArch", catalogCpuArch);
    } catch (Exception e) {
      logger.error("Could not fetch catalog service CPU arch: {}", e.getMessage());
      model.addAttribute("catalogCpuArch", "N/A");
    }

    try {
      String reviewCpuArch = restTemplate.getForObject(reviewApiUrl + "/arch", String.class);
      model.addAttribute("reviewCpuArch", reviewCpuArch);
    } catch (Exception e) {
      logger.error("Could not fetch review service CPU arch: {}", e.getMessage());
      model.addAttribute("reviewCpuArch", "N/A");
    }

    return "index";
  }

  @GetMapping("/books")
  public String getPaginatedBooks(
      Model model,
      @RequestParam(defaultValue = "0") int page,
      @RequestParam(defaultValue = "10") int size) {
    try {
      String url =
          UriComponentsBuilder.fromHttpUrl(bookApiUrl)
              .queryParam("page", page)
              .queryParam("size", size)
              .toUriString();

      ParameterizedTypeReference<RestPage<BookDto>> responseType =
          new ParameterizedTypeReference<>() {};
      Page<BookDto> bookPage =
          restTemplate.exchange(url, HttpMethod.GET, null, responseType).getBody();
      model.addAttribute("bookPage", bookPage);
      model.addAttribute("listTitle", "Full Book Catalog (Paginated)");
    } catch (Exception e) {
      logger.error("Could not fetch paginated books: {}", e.getMessage());
      model.addAttribute("bookPage", Page.empty());
      model.addAttribute("serviceError", "The Book Catalog service is currently unavailable.");
    }
    return "book-list";
  }

  @GetMapping("/books/all")
  public String getAllBooks(Model model) {
    try {
      ParameterizedTypeReference<List<BookDto>> responseType =
          new ParameterizedTypeReference<>() {};
      List<BookDto> books =
          restTemplate.exchange(bookApiUrl + "/all", HttpMethod.GET, null, responseType).getBody();

      model.addAttribute(
          "bookPage", new PageImpl<>(books == null ? Collections.emptyList() : books));
      model.addAttribute("listTitle", "Full Book Catalog (All)");
    } catch (Exception e) {
      logger.error("Could not fetch all books: {}", e.getMessage());
      model.addAttribute("bookPage", Page.empty());
      model.addAttribute("serviceError", "The Book Catalog service is currently unavailable.");
    }
    return "book-list";
  }

  @GetMapping("/books/popular")
  public String getPopularBooks(Model model) {
    try {
      ParameterizedTypeReference<List<BookDto>> responseType =
          new ParameterizedTypeReference<>() {};
      List<BookDto> books =
          restTemplate
              .exchange(bookApiUrl + "/popular", HttpMethod.GET, null, responseType)
              .getBody();

      model.addAttribute(
          "bookPage", new PageImpl<>(books == null ? Collections.emptyList() : books));
      model.addAttribute("listTitle", "Popular Books (from Redis)");
    } catch (Exception e) {
      logger.error("Could not fetch popular books from catalog service: {}", e.getMessage());
      model.addAttribute("bookPage", Page.empty());
      model.addAttribute("serviceError", "The Book Catalog service is currently unavailable.");
    }
    return "book-list";
  }

  @GetMapping("/book/{isbn}")
  public String getBookByIsbn(@PathVariable String isbn, Model model) {
    try {
      BookDto book = restTemplate.getForObject(bookApiUrl + "/" + isbn, BookDto.class);
      model.addAttribute("book", book);
      model.addAttribute("newReviewDto", new ReviewDto(isbn));
    } catch (HttpClientErrorException.NotFound e) {
      return "redirect:/books";
    } catch (Exception e) {
      logger.error("Could not fetch book {}: {}", isbn, e.getMessage());
      model.addAttribute("serviceError", "The Book Catalog service is currently unavailable.");
      return "book-detail";
    }

    try {
      List<ReviewDto> reviews =
          restTemplate
              .exchange(
                  reviewApiUrl + "/" + isbn,
                  HttpMethod.GET,
                  null,
                  new ParameterizedTypeReference<List<ReviewDto>>() {})
              .getBody();
      model.addAttribute("reviews", reviews);
    } catch (Exception e) {
      logger.error("Could not fetch reviews for book {}: {}", isbn, e.getMessage());
      model.addAttribute("reviewError", "The Review service is currently unavailable.");
    }

    return "book-detail";
  }

  @GetMapping("/books/new")
  public String showAddBookForm(Model model) {
    model.addAttribute("book", new BookDto(null, null, null, 0, null));
    return "book-form";
  }

  @PostMapping("/books")
  public String addBook(@ModelAttribute BookDto book) {
    restTemplate.postForObject(bookApiUrl, book, BookDto.class);
    return "redirect:/books";
  }

  @PostMapping("/book/delete/{isbn}")
  public String deleteBook(@PathVariable String isbn) {
    restTemplate.delete(bookApiUrl + "/" + isbn);
    return "redirect:/books";
  }

  @PostMapping("/reviews")
  public String addReview(@ModelAttribute ReviewDto newReview) {
    restTemplate.postForObject(reviewApiUrl, newReview, ReviewDto.class);
    return "redirect:/book/" + newReview.bookIsbn();
  }

  @PostMapping("/reviews/delete/{id}")
  public String deleteReview(@PathVariable Long id, @RequestParam String bookIsbn) {
    try {
      restTemplate.delete(reviewApiUrl + "/" + id);
    } catch (Exception e) {
      logger.error("Could not delete review {}: {}", id, e.getMessage());
    }
    return "redirect:/book/" + bookIsbn;
  }

  @GetMapping("/bulk-upload")
  public String showBulkUploadForm() {
    return "bulk-upload";
  }

  @PostMapping("/upload/books")
  public String handleBookUpload(
      @RequestParam("file") MultipartFile file, RedirectAttributes redirectAttributes) {
    if (file.isEmpty()) {
      redirectAttributes.addFlashAttribute("errorMessage", "Please select a file to upload.");
      return "redirect:/bulk-upload";
    }

    List<BookDto> books = new ArrayList<>();
    try (Reader reader = new InputStreamReader(file.getInputStream());
        CSVReader csvReader = new CSVReader(reader)) {
      String[] line;
      while ((line = csvReader.readNext()) != null) {
        BookDto book = new BookDto(line[0], line[1], line[2], Integer.parseInt(line[3]), line[4]);
        books.add(book);
      }
    } catch (IOException | CsvValidationException | NumberFormatException e) {
      logger.error("Error parsing book CSV file", e);
      redirectAttributes.addFlashAttribute(
          "errorMessage", "Error parsing CSV file: " + e.getMessage());
      return "redirect:/bulk-upload";
    }

    try {
      restTemplate.postForObject(bookApiUrl + "/batch", books, String.class);
      redirectAttributes.addFlashAttribute(
          "successMessage", books.size() + " books uploaded successfully!");
    } catch (Exception e) {
      logger.error("Error sending books to backend", e);
      redirectAttributes.addFlashAttribute("errorMessage", "API Error: Could not upload books.");
    }

    return "redirect:/bulk-upload";
  }

  @PostMapping("/upload/reviews")
  public String handleReviewUpload(
      @RequestParam("file") MultipartFile file, RedirectAttributes redirectAttributes) {
    if (file.isEmpty()) {
      redirectAttributes.addFlashAttribute("errorMessage", "Please select a file to upload.");
      return "redirect:/bulk-upload";
    }
    List<ReviewDto> reviews = new ArrayList<>();
    try (Reader reader = new InputStreamReader(file.getInputStream());
        CSVReader csvReader = new CSVReader(reader)) {
      String[] line;
      while ((line = csvReader.readNext()) != null) {
        ReviewDto review =
            new ReviewDto(null, line[0], line[1], Integer.parseInt(line[2]), line[3], null);
        reviews.add(review);
      }
    } catch (IOException | CsvValidationException | NumberFormatException e) {
      logger.error("Error parsing review CSV file", e);
      redirectAttributes.addFlashAttribute(
          "errorMessage", "Error parsing CSV file: " + e.getMessage());
      return "redirect:/bulk-upload";
    }

    try {
      restTemplate.postForObject(reviewApiUrl + "/batch", reviews, String.class);
      redirectAttributes.addFlashAttribute(
          "successMessage", reviews.size() + " reviews uploaded successfully!");
    } catch (Exception e) {
      logger.error("Error sending reviews to backend", e);
      redirectAttributes.addFlashAttribute("errorMessage", "API Error: Could not upload reviews.");
    }
    return "redirect:/bulk-upload";
  }

  @PostMapping("/upload/popular")
  public String handlePopularUpload(
      @RequestParam("file") MultipartFile file, RedirectAttributes redirectAttributes) {
    if (file.isEmpty()) {
      redirectAttributes.addFlashAttribute("errorMessage", "Please select a file to upload.");
      return "redirect:/bulk-upload";
    }
    List<String> isbns = new ArrayList<>();
    try (Reader reader = new InputStreamReader(file.getInputStream());
        CSVReader csvReader = new CSVReader(reader)) {
      String[] line;
      while ((line = csvReader.readNext()) != null) {
        isbns.add(line[0]);
      }
    } catch (IOException | CsvValidationException e) {
      logger.error("Error parsing popular ISBNs CSV file", e);
      redirectAttributes.addFlashAttribute(
          "errorMessage", "Error parsing CSV file: " + e.getMessage());
      return "redirect:/bulk-upload";
    }

    try {
      restTemplate.postForObject(bookApiUrl + "/popular/batch", isbns, String.class);
      redirectAttributes.addFlashAttribute(
          "successMessage", isbns.size() + " ISBNs submitted to popular list.");
    } catch (Exception e) {
      logger.error("Error sending popular ISBNs to backend", e);
      redirectAttributes.addFlashAttribute(
          "errorMessage", "API Error: Could not upload popular ISBNs.");
    }
    return "redirect:/bulk-upload";
  }

  @PostMapping("/cleanup/reviews")
  public String cleanupTestReviews(RedirectAttributes redirectAttributes) {
    try {
      String cleanupUrl = reviewApiUrl + "/cleanup-k6-tests";
      ResponseEntity<String> response =
          restTemplate.exchange(cleanupUrl, HttpMethod.DELETE, null, String.class);
      redirectAttributes.addFlashAttribute("successMessage", response.getBody());
    } catch (Exception e) {
      logger.error("Error during k6 review cleanup", e);
      redirectAttributes.addFlashAttribute(
          "errorMessage", "API Error: Could not clean up test reviews.");
    }
    return "redirect:/bulk-upload";
  }
}
