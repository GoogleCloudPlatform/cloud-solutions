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
 * limitations under the License
 */

/** @fileoverview Defines the entrypoints for all the Cloud Functions. */

export {
  handleHttpRequest as pollerHandleHttpRequest,
  handleLocalConfig as pollerHandleLocalConfig,
  handlePubSubRequest as pollerHandlePubSubRequest,
} from './poller/index';

export {
  handleHttpRequest as forwarderHandleHttpRequest,
  handlePubSubRequest as forwarderHandlePubSubRequest,
} from './forwarder/index';

export {
  handlePubSubRequest as scalerHandlePubSubRequest,
  handleLocalConfig as scalerHandleLocalConfig,
  handleHttpRequest as scalerHandleHttpRequest,
} from './scaler/index';
