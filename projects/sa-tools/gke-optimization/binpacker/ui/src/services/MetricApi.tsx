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
import axios, { AxiosResponse } from 'axios';
import {
  MetricFetchAllResponse,
  MetricFetchAllRequest,
} from '../../proto/metric.pb';

const currentHost = `${window.location.protocol}//${window.location.hostname}`;

export const metricFetchAll = async (
  request: MetricFetchAllRequest
): Promise<MetricFetchAllResponse> => {
  const response = await axios.post<
    MetricFetchAllRequest,
    AxiosResponse<MetricFetchAllResponse>
  >(
    `${currentHost}/api/metrics`,
    {
      projectId: request.projectId,
    },
    {
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );
  return response.data;
};
