/**
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

/** @fileoverview Executes a scaling request. */

import {ScalableInstanceWithData} from '../common/instance-info';

/** Executes the scaling operation to the suggested size. */
export interface IScalerExecutor {
  /**
   * Executes the scaling operation to the suggested size.
   * @return Operation id (operation name) or null.
   */
  scaleInstance(
    instance: ScalableInstanceWithData,
    suggestedSize: number
  ): Promise<string | null>;
}
