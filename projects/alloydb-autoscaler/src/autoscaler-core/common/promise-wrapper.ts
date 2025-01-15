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

/** @fileoverview Provides a Promise wrapper with providers. */

/** A promise with resolvers. */
export interface PromiseWithResolvers<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  reject: (reason: any) => void;
}

/**
 * Node version of ECMA262's Promise.withResolvers()
 * @see https://tc39.es/proposal-promise-with-resolvers/#sec-promise.withResolvers
 *
 * @return Promise, with resolvesrs installed.
 */
export function promiseWithResolvers<T>(): PromiseWithResolvers<T> {
  let resolve: (value: T) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let reject: (reason: any) => void;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  // @ts-expect-error used-before-assigned
  return {promise, resolve, reject};
}

/**
 * Sleeps for the required time.
 * Usage: wait sleep(3000); // Sleeps 3 seconds.
 * @param millisToSleep Milliseconds to sleep.
 */
export async function sleep(millisToSleep: number) {
  return new Promise(resolve => setTimeout(resolve, millisToSleep));
}
