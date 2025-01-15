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

/** @fileoverview Provides the entrypoint definitions. */

import {Request, Response} from 'express';

/** Environment variables. Used mostly for testing. */
export type EnvironmentVariables = Record<string, string>;

/**
 * A basic entrypoint function.
 * @param payload The payload received by the function (in string format).
 */
export type EntrypointHandler = (payload: string) => void;

/**
 * A basic HTTP handler.
 * @param req HTTP Request (express).
 * @param res HTTP Response (express).
 */
export type HttpHandler = (req: Request, res: Response) => void;

/**
 * A basic PubSub handler.
 * @param pubSubEvent Event received from PubSub.
 *   Event contains a {data} parameter with the payload.
 * @param context Context provided by the PubSub. This is not in use, but its
 *   type and usage is not under our control.
 */
export type PubSubHandler = (
  pubSubEvent: {
    data: string;
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  context: any
) => void;

/** A builder to provide Cloud Function entrypoints. */
export interface EntrypointBuilder {
  buildRequestHandler(): EntrypointHandler;
  buildRequestHandlerForHttpRequests(
    payload: string,
    env?: EnvironmentVariables
  ): HttpHandler;
  buildRequestHandlerForPubSub(): PubSubHandler;
}

/** Provides common utility for creating entrypoints. */
export class BaseEntrypointBuilder {
  /** Sets the environment variables. Used mostly for testing. */
  setEnvironmentVariables(env?: EnvironmentVariables) {
    if (env) {
      Object.entries(env).forEach(([key, value]) => {
        process.env[key] = value;
      });
    }
  }
}
