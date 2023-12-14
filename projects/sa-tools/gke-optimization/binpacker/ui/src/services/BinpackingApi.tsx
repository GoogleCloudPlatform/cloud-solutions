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
  BinpackingCalculateRequest,
  BinpackingCalculateResponse,
} from '../../proto/binpacking.pb';

const currentHost = `${window.location.protocol}//${window.location.hostname}`;

export const binpackingCalculate = async (
  request: BinpackingCalculateRequest
): Promise<BinpackingCalculateResponse> => {
  const response = await axios.post<
    BinpackingCalculateRequest,
    AxiosResponse<BinpackingCalculateResponse>
  >(`${currentHost}/api/binpacker`, request, {
    headers: {
      'Content-Type': 'application/json',
    },
  });
  return response.data;
};
