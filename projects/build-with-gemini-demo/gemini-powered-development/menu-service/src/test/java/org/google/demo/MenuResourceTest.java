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

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.mockito.ArgumentMatchers.any;

import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.mockito.InjectMock;
import io.restassured.http.ContentType;
import java.math.BigDecimal;
import java.util.Collections;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

/** Test class for MenuResource. */
@QuarkusTest
public class MenuResourceTest {

  @InjectMock MenuRepository menuRepository;

  /** Sets up the test environment before each test. */
  @BeforeEach
  public void setup() {
    Menu menu = new Menu();
    menu.id = 1L;
    menu.itemName = "Test Item";
    menu.itemPrice = BigDecimal.valueOf(10.0);
    menu.spiceLevel = 1;
    menu.tagLine = "Test Tagline";
    menu.itemImageUrl = null; // Set to null or a valid URL
    menu.itemThumbnailUrl = null; // Set to null or a valid URL
    menu.status = Status.Ready;

    Mockito.when(menuRepository.findById(1L)).thenReturn(menu);
    Mockito.when(menuRepository.listAll()).thenReturn(Collections.singletonList(menu));
    Mockito.doAnswer(
            invocation -> {
              Menu m = invocation.getArgument(0);
              m.id = 1L;
              return null;
            })
        .when(menuRepository)
        .persist(any(Menu.class));
  }

  /** Tests the creation of a menu item. */
  @Test
  public void testCreateMenu() {
    Menu menu = new Menu();
    menu.itemName = "Test Item";
    menu.itemPrice = java.math.BigDecimal.valueOf(10.0);
    menu.spiceLevel = 1;
    menu.tagLine = "Test Tagline";
    menu.itemImageUrl = null; // Set to null or a valid URL
    menu.itemThumbnailUrl = null; // Set to null or a valid URL
    menu.status = Status.Ready;

    given()
        .contentType(ContentType.JSON)
        .body(menu)
        .when()
        .post("/menu")
        .then()
        .statusCode(200)
        .body("id", notNullValue())
        .body("itemName", is("Test Item"));
  }
}
