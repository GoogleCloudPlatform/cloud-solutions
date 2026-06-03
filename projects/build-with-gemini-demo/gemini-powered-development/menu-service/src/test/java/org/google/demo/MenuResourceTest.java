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
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.notNullValue;
import static org.mockito.ArgumentMatchers.any;

import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.mockito.InjectMock;
import io.restassured.http.ContentType;
import java.math.BigDecimal;
import java.util.Collections;
import java.util.Arrays;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

/** Test class for MenuResource. */
@QuarkusTest
public class MenuResourceTest {

  @InjectMock MenuRepository menuRepository;

  private Menu testMenu;

  /** Sets up the test environment before each test. */
  @BeforeEach
  public void setup() {
    testMenu = new Menu();
    testMenu.id = 1L;
    testMenu.itemName = "Test Item";
    testMenu.description = "Test Description";
    testMenu.rating = 5;
    testMenu.itemPrice = BigDecimal.valueOf(10.0);
    testMenu.spiceLevel = 1;
    testMenu.tagLine = "Test Tagline";
    testMenu.status = Status.Ready;

    Mockito.when(menuRepository.findById(1L)).thenReturn(testMenu);
    Mockito.when(menuRepository.listAll(any())).thenReturn(Collections.singletonList(testMenu));
    Mockito.when(menuRepository.list("status", Status.Ready)).thenReturn(Collections.singletonList(testMenu));
    Mockito.when(menuRepository.list("status", Status.Failed)).thenReturn(Collections.emptyList());
    Mockito.when(menuRepository.list("status", Status.Processing)).thenReturn(Collections.emptyList());

    Mockito.doAnswer(
            invocation -> {
              Menu m = invocation.getArgument(0);
              m.id = 1L;
              return null;
            })
        .when(menuRepository)
        .persist(any(Menu.class));
  }

  /** Tests retrieving all menu items. */
  @Test
  public void testGetAll() {
    given()
        .when()
        .get("/menu")
        .then()
        .statusCode(200)
        .body("size()", is(1))
        .body("[0].itemName", is("Test Item"));
  }

  /** Tests retrieving a single menu item by ID. */
  @Test
  public void testGetById() {
    given()
        .pathParam("id", 1L)
        .when()
        .get("/menu/{id}")
        .then()
        .statusCode(200)
        .body("itemName", is("Test Item"))
        .body("description", is("Test Description"))
        .body("rating", is(5));
  }

  /** Tests retrieving menu items by status. */
  @Test
  public void testGetByStatus() {
    given()
        .when()
        .get("/menu/ready")
        .then()
        .statusCode(200)
        .body("size()", is(1));

    given()
        .when()
        .get("/menu/failed")
        .then()
        .statusCode(200)
        .body("size()", is(0));

    given()
        .when()
        .get("/menu/processing")
        .then()
        .statusCode(200)
        .body("size()", is(0));
  }

  /** Tests the creation of a menu item. */
  @Test
  public void testCreateMenu() {
    Menu menu = new Menu();
    menu.itemName = "New Item";
    menu.description = "New Description";
    menu.rating = 4;
    menu.itemPrice = BigDecimal.valueOf(15.0);
    menu.spiceLevel = 2;
    menu.tagLine = "New Tagline";

    given()
        .contentType(ContentType.JSON)
        .body(menu)
        .when()
        .post("/menu")
        .then()
        .statusCode(200)
        .body("id", notNullValue())
        .body("itemName", is("New Item"))
        .body("description", is("New Description"))
        .body("rating", is(4))
        .body("status", is("Processing"));
  }

  /** Tests rating validation on creation. */
  @Test
  public void testCreateMenuInvalidRating() {
    Menu menu = new Menu();
    menu.itemName = "Invalid Rating";
    menu.rating = 0; // Invalid, min is 1

    given()
        .contentType(ContentType.JSON)
        .body(menu)
        .when()
        .post("/menu")
        .then()
        .statusCode(400);

    menu.rating = 6; // Invalid, max is 5
    given()
        .contentType(ContentType.JSON)
        .body(menu)
        .when()
        .post("/menu")
        .then()
        .statusCode(400);

    menu.rating = null; // Invalid, NotNull
    given()
        .contentType(ContentType.JSON)
        .body(menu)
        .when()
        .post("/menu")
        .then()
        .statusCode(400);
  }

  /** Tests updating a menu item. */
  @Test
  public void testUpdateMenu() {
    Menu updateData = new Menu();
    updateData.itemName = "Updated Name";
    updateData.rating = 3;
    updateData.description = "Updated Description";

    given()
        .pathParam("id", 1L)
        .contentType(ContentType.JSON)
        .body(updateData)
        .when()
        .put("/menu/{id}")
        .then()
        .statusCode(200)
        .body("itemName", is("Updated Name"))
        .body("rating", is(3))
        .body("description", is("Updated Description"));
  }

  /** Tests deleting a menu item. */
  @Test
  public void testDeleteMenu() {
    given()
        .pathParam("id", 1L)
        .when()
        .delete("/menu/{id}")
        .then()
        .statusCode(204);

    Mockito.verify(menuRepository).delete(any(Menu.class));
  }
}
