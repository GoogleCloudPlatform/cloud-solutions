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

import { describe, expect, it } from 'vitest';
import * as common from './Common/CommonFunctions';

const commonFunctionsTestSuite = () => {
  it('checkAndExecuteFn valid get arguments,', () => {
    const fn = (a1, a2) => `${a1}-${a2}`;
    const actualReturn = common.checkAndExecuteFn(fn, 'a', 'b');

    expect(actualReturn).toEqual('a-b');
  });

  it('checkAndExecuteFn, valid function, no arguments', () => {
    const fn = (a1, a2) => `args-${a1}-${a2}`;
    const actualReturn = common.checkAndExecuteFn(fn);

    expect(actualReturn).toEqual('args-undefined-undefined');
  });

  it('checkAndExecuteFn, invalid function, arguments', () => {
    const fn = '';
    const actualReturn = common.checkAndExecuteFn(fn, 'a', 'b');

    expect(actualReturn).toBeUndefined();
  });

  it('checkAndExecuteFn, undefined function, arguments', () => {
    let fn;
    const actualReturn = common.checkAndExecuteFn(fn, 'a', 'b');

    expect(actualReturn).toBeUndefined();
  });

  it('checkAndExecuteFn, null function, arguments', () => {
    expect(common.checkAndExecuteFn(null, 'a', 'b')).toBeUndefined();
  });
};

describe('CommonFunctions Test suite', commonFunctionsTestSuite);
