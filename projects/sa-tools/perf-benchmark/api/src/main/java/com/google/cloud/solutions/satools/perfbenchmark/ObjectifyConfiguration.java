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

import com.google.cloud.solutions.satools.common.objectifyextensions.ObjectifyFilter;
import com.googlecode.objectify.ObjectifyService;
import jakarta.servlet.ServletContextEvent;
import jakarta.servlet.ServletContextListener;
import jakarta.servlet.annotation.WebListener;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.boot.web.servlet.ServletListenerRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** SpringBoot registrations for using Objectify. */
@Configuration
public class ObjectifyConfiguration {

  /** Simple all parameter constructor. */
  @Bean
  public FilterRegistrationBean<ObjectifyFilter> objectifyFilterRegistration() {
    final FilterRegistrationBean<ObjectifyFilter> registration = new FilterRegistrationBean<>();
    registration.setFilter(new ObjectifyFilter());
    registration.addUrlPatterns("/benchmarkjobs/*", "/buildstatus/*");
    registration.setOrder(1);
    return registration;
  }

  /** Returns a Spring Bean to register the Objectify Listener. */
  @Bean
  public ServletListenerRegistrationBean<ObjectifyListener> listenerRegistrationBean() {
    ServletListenerRegistrationBean<ObjectifyListener> bean =
        new ServletListenerRegistrationBean<>();
    bean.setListener(new ObjectifyListener());
    return bean;
  }

  /** Provides a listener bean to instantiate Objectify for each servlet request. */
  @WebListener
  public static class ObjectifyListener implements ServletContextListener {

    @Override
    public void contextInitialized(ServletContextEvent sce) {
      ObjectifyService.init();
      DatastoreService.registerEntities();
    }
  }
}
