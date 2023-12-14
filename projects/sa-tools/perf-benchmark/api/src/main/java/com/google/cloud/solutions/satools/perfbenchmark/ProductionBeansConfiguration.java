/*
 * Copyright 2023 Google LLC
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

package com.google.cloud.solutions.satools.perfbenchmark;

import com.google.cloud.solutions.satools.common.auth.GoogleAccessTokenService;
import com.google.cloud.solutions.satools.common.auth.GoogleImpersonatedCredentialService;
import com.google.cloud.solutions.satools.common.auth.GoogleMetadataService;
import com.google.cloud.solutions.satools.common.auth.GoogleTokenInfoService;
import com.google.cloud.solutions.satools.common.auth.ImpersonatedCredentialService;
import com.google.cloud.solutions.satools.common.auth.TokenInfoService;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.BigQueryClientFactory;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.CloudBuildClientServiceFactory;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.StorageClientServiceFactory;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Clock;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.web.context.annotation.RequestScope;

/** Spring Beans configuration for production environment. */
@Configuration
@Profile("production")
public class ProductionBeansConfiguration {

  @Bean
  Clock systemClockBean() {
    return Clock.systemUTC();
  }

  @Bean
  GoogleTokenInfoService googleTokeninfoService() {
    return new GoogleTokenInfoService();
  }

  @Bean
  @RequestScope
  GoogleAccessTokenService accessTokenCredentialService(
      @Autowired HttpServletRequest request, @Autowired TokenInfoService tokeninfoService) {

    return new GoogleAccessTokenService(request, tokeninfoService);
  }

  @Bean
  @RequestScope
  ImpersonatedCredentialService impersonatedCredentialService(
      @Autowired GoogleAccessTokenService accessTokenCredentialService) {
    return new GoogleImpersonatedCredentialService(
        accessTokenCredentialService, GoogleMetadataService.create());
  }

  @Bean
  CloudBuildClientServiceFactory cloudBuildClientServiceFactory(
      @Autowired UserAgentHeaderProvider uaHeaderProvider) {
    return new CloudBuildClientServiceFactory(uaHeaderProvider);
  }

  @Bean
  BigQueryClientFactory bigQueryClientFactory(@Autowired UserAgentHeaderProvider uaHeaderProvider) {
    return new BigQueryClientFactory(uaHeaderProvider);
  }

  @Bean
  StorageClientServiceFactory storageClientServiceFactory(
      @Autowired UserAgentHeaderProvider uaHeaderProvider) {
    return new StorageClientServiceFactory(uaHeaderProvider);
  }

  @Bean
  GoogleMetadataService metadataService() {
    return GoogleMetadataService.create();
  }
}
