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

/** @fileoverview Tests for promise-wrapper. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {promiseWithResolvers, sleep} from '../promise-wrapper';

describe('promise-wrapper', () => {
  describe('promiseWithResolvers', () => {
    it('creates a promise with a resolver', async () => {
      const promise = promiseWithResolvers();
      promise.resolve(null);

      await expectAsync(promise.promise).toBeResolvedTo(null);
    });

    it('creates a promise with a reject', async () => {
      const promise = promiseWithResolvers();
      promise.reject(new Error('Rejected.'));

      await expectAsync(promise.promise).toBeRejectedWithError();
    });
  });

  describe('sleep', () => {
    beforeEach(() => {
      jasmine.clock().install();
    });

    afterEach(() => {
      jasmine.clock().uninstall();
    });

    it('waits required seconds', async () => {
      const sleepPromise = sleep(1000);

      await expectAsync(sleepPromise).toBePending();
      jasmine.clock().tick(999); // Tick less than the time, still pending.
      await expectAsync(sleepPromise).toBePending();
      jasmine.clock().tick(2); // Tick more than the time, resolved.
      await expectAsync(sleepPromise).toBeResolved();
    });
  });
});
