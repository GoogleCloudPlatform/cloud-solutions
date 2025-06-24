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

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.io.Serializable;

@Entity
@Table(name = "books")
public class Book implements Serializable { // Serializable for Redis caching

  @Id
  @NotNull
  @Size(min = 10, max = 13)
  @Pattern(regexp = "^[0-9-]*$", message = "ISBN must contain only numbers and dashes")
  @Column(nullable = false, updatable = false)
  private String isbn;

  @NotNull
  @Size(min = 1, max = 255)
  @Pattern(regexp = "^[\\w\\s.,'-:]*$", message = "Title contains invalid characters")
  private String title;

  @NotNull
  @Size(min = 1, max = 255)
  @Pattern(regexp = "^[\\w\\s.,'-]*$", message = "Author contains invalid characters")
  private String author;

  @Min(1000)
  private int publicationYear;

  @Size(max = 100)
  @Pattern(regexp = "^[\\w\\s-]*$", message = "Genre contains invalid characters")
  private String genre;

  // Default constructor for JPA
  public Book() {}

  // Constructor for easy object creation
  public Book(String isbn, String title, String author, int publicationYear, String genre) {
    this.isbn = isbn;
    this.title = title;
    this.author = author;
    this.publicationYear = publicationYear;
    this.genre = genre;
  }

  // Getters and Setters...
  public String getIsbn() {
    return isbn;
  }

  public void setIsbn(String isbn) {
    this.isbn = isbn;
  }

  public String getTitle() {
    return title;
  }

  public void setTitle(String title) {
    this.title = title;
  }

  public String getAuthor() {
    return author;
  }

  public void setAuthor(String author) {
    this.author = author;
  }

  public int getPublicationYear() {
    return publicationYear;
  }

  public void setPublicationYear(int publicationYear) {
    this.publicationYear = publicationYear;
  }

  public String getGenre() {
    return genre;
  }

  public void setGenre(String genre) {
    this.genre = genre;
  }
}
