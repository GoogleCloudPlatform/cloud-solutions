/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import {Pod} from '../../../proto/metric.pb';

export type Workload = {
  name: string;
  type: string;
  namespace: string;
  replicas: number;
  cpuRequest: number;
  cpuLimit: number;
  memoryRequest: number;
  memoryLimit: number;
  memoryRequestInMiB: number;
  memoryLimitInMiB: number;
};

export type PodExtended = Pod & {
  memoryRequestInMiB: number;
  memoryLimitInMiB: number;
};
