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

import static com.google.cloud.solutions.satools.common.utils.SixtyTwoSymbols.sixtyTwoSymbols;

import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkJob;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.JobInformation;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.ListBenchmarkJobs;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/benchmarkjobs")
class BenchmarkJobController {

  @Autowired private BenchmarkJobDbService benchmarkJobDbService;
  @Autowired private CloudBuildJobService cloudBuildJobService;

  @PostMapping
  BenchmarkJob create(@RequestBody JobInformation jobInformation, HttpServletResponse response)
      throws Exception {
    var runKey = DatastoreService.ofy().factory().allocateId(BenchmarkJobEntity.class);
    var buildInfo = cloudBuildJobService.create(jobInformation, sixtyTwoSymbols(runKey.getId()));
    return benchmarkJobDbService.create(runKey.getId(), jobInformation, buildInfo);
  }

  @GetMapping("/{jobId}")
  BenchmarkJob get(@PathVariable long jobId) {
    return benchmarkJobDbService.retrieve(jobId);
  }

  @GetMapping
  ListBenchmarkJobs listAllJobs() {
    return benchmarkJobDbService.retrieveAllUserJobs();
  }

  @GetMapping("/{jobId}:cancel")
  BenchmarkJob cancel(@PathVariable long jobId) throws IOException {
    var job = benchmarkJobDbService.getJobEntity(jobId);
    cloudBuildJobService.cancel(job.getCloudBuildJobId());
    return benchmarkJobDbService.cancel(jobId);
  }
}
