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
import { SaToolsDate } from './Common/SaToolsDate';

const satoolsDateTestSuite = () => {
  it(`Given N number of substracted minutes should return new Date object of
    N minutes ago`, () => {
    const n = 22; // 22 minutes
    const today = new Date();
    const dateUtil = new SaToolsDate(today);
    const diff = dateUtil.subtractMinutes(n);
    if (diff.getHours() < today.getHours()) {
      expect(today.getMinutes() + 60 - diff.getMinutes()).toBe(n);
    } else {
      expect(today.getMinutes() - diff.getMinutes()).toBe(n);
    }
  });

  it(`Given N number of substracted hours should return new Date object of
    N hours ago`, () => {
    const today = new Date();
    const dateUtil = new SaToolsDate(today);
    expect(today - dateUtil.subtractHours(3)).toBe(10_800_000);
  });

  it(`Given compared date string one hour from now should return 1 hour(s)
    ago`, () => {
    const testDate = new SaToolsDate(new Date('2022-12-01 11:00:00'));
    expect(testDate.formattedDateDiff(new Date('2022-12-01 10:00:00')))
        .toBe('1 hour(s) ago');
  });

  it(`Given compared date string 24 hour from now should return
    Yesterday`, () => {
    const dateUtil = new SaToolsDate();
    const diff = dateUtil.subtractHours(24); // 24 hours
    expect(dateUtil.formattedDateDiff(diff)).toBe('Yesterday');
  });

  it(`Given compared date string 35 hour from now should return
    Yesterday`, () => {
    const dateUtil = new SaToolsDate();
    const diff = dateUtil.subtractHours(35); // 35 hours
    expect(dateUtil.formattedDateDiff(diff)).toBe('Yesterday');
  });

  it(`Given compared date string 3 days ago from 2023-02-10
    should return 7 Feb 2023`, () => {
    const dateUtil = new SaToolsDate(new Date('2023-02-10'));
    const diff = dateUtil.subtractHours(72); // 3 days ago
    expect(dateUtil.formattedDateDiff(diff))
        .toBe('Feb 7, 2023, 12:00 AM');
  });

  it(`Given compared date string 15 minutes from now should
    return 15 minute(s) ago`, () => {
    const dateUtil = new SaToolsDate();
    const diff = dateUtil.subtractMinutes(15); // 15 minutes
    expect(dateUtil.formattedDateDiff(diff))
        .toBe('15 minute(s) ago');
  });

  it(`Given compared date string 50 minutes from now should
    return 50 minute(s) ago`, () => {
    const dateUtil = new SaToolsDate();
    const diff = dateUtil.subtractMinutes(50); // 50 minutes
    expect(dateUtil.formattedDateDiff(diff))
        .toBe('50 minute(s) ago');
  });

  it(`Given a date in Date type should return new medium date
    format`, () => {
    const dateUtil = new SaToolsDate();
    const diff = dateUtil.mediumDateFormat(new Date('2023-02-11 02:15'));
    expect(diff).toBe('Feb 11, 2023, 2:15 AM');
  });

  it(`Given a date in string type should return new medium or
    long date format`, () => {
    const dateUtil = new SaToolsDate();
    const diff = dateUtil.formattedDateDiffStr(new Date('2023-02-11 02:15'));
    expect(diff).toBe('Feb 11, 2023, 2:15 AM');
  });

  it(`Given datetime today should return today's datetime in
    medium format`, () => {
    const dateUtil = new SaToolsDate();
    const today = new Date();
    const diff = dateUtil.formattedDateDiffStr(today);
    expect(diff).toBe('0 minute(s) ago');
  });

  it(`Given a datetime in 50 mins ago should return 50 minute(s) ago`,
      () => {
        const testDate = new SaToolsDate(new Date('2022-12-01 10:10:00'));
        expect(testDate.formattedDateDiffFrom(
            new Date('2022-12-01 11:00:00')),
        ).toBe('50 minute(s) ago');
      });

  it('fromUnixSeconds valid', () => {
    const testDate = SaToolsDate.fromUnixSeconds(1683186224);
    expect(testDate.date).toEqual(new Date('2023-05-04 07:43:44Z'));
  });
};

describe('SaToolsDate TestSuite', satoolsDateTestSuite);
