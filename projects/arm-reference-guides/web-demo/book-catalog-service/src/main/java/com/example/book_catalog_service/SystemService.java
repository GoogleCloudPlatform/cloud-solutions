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

import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

@Service
public class SystemService {

  private String cpuArch;

  @PostConstruct
  public void init() {
    this.cpuArch = System.getProperty("os.arch");
  }

  public String getCpuArch() {
    return cpuArch;
  }
}
