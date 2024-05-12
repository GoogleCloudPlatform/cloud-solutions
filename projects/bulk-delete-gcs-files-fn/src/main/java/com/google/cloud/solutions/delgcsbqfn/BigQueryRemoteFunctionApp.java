/*
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.google.cloud.solutions.delgcsbqfn;

import com.google.cloud.solutions.delgcsbqfn.BigQueryRemoteFn.BigQueryRemoteFnRequest;
import com.google.cloud.solutions.delgcsbqfn.BigQueryRemoteFn.BigQueryRemoteFnResponse;
import com.google.common.flogger.GoogleLogger;
import org.apache.coyote.http11.AbstractHttp11Protocol;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.embedded.tomcat.TomcatServletWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * Wrapper Springboot application to provide an endpoint compatible with BigQuery Remote functions.
 */
@SpringBootApplication
@RestController
public class BigQueryRemoteFunctionApp {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  @Autowired BigQueryRemoteFn bqfn;

  /**
   * The main REST Controller that provides BigQuery Remote function compliant endpoint.
   *
   * @see <a
   *     href="https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#create_a_http_endpoint_in_or>Remote
   *     function HTTP Endpoint</a>
   */
  @PostMapping("/")
  public ResponseEntity<BigQueryRemoteFnResponse> process(
      @RequestBody BigQueryRemoteFnRequest request) {
    try {
      return ResponseEntity.ok(bqfn.process(request));
    } catch (RuntimeException exp) {
      logger.atInfo().withCause(exp).log("error processing request");
      return ResponseEntity.internalServerError()
          .body(BigQueryRemoteFnResponse.withErrorMessage(exp.getCause().getClass().getName()));
    }
  }

  /** Add Spring bean to enable Keep-Alive HTTP Response header. */
  @Bean
  public WebServerFactoryCustomizer<TomcatServletWebServerFactory> tomcatCustomizer() {
    return (tomcat) ->
        tomcat.addConnectorCustomizers(
            (connector) -> {
              if (connector.getProtocolHandler()
                  instanceof AbstractHttp11Protocol<?> protocolHandler) {
                protocolHandler.setKeepAliveTimeout(300000);
                protocolHandler.setMaxKeepAliveRequests(100);
                protocolHandler.setUseKeepAliveResponseHeader(true);
              }
            });
  }

  /**
   * The main entry point of the SpringBoot application.
   *
   * @param args the command line arguments for the application.
   */
  public static void main(String[] args) {
    SpringApplication.run(BigQueryRemoteFunctionApp.class, args);
  }
}
