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

/**
  * Helper class on date formatting.
  * @param {Date=} dateObj
  */
class SaToolsDate {
  /**
   * @param {Date=} dateObj
   */
  constructor(dateObj = new Date()) {
    this.date = dateObj;
  }

  /**
   * Creates an instance from unix seconds
   *
   * @param {!number} utcUnixSeconds
   * @return {!SaToolsDate}
   */
  static fromUnixSeconds(utcUnixSeconds) {
    return new SaToolsDate(new Date(utcUnixSeconds * 1000));
  }

  /**
   * @return {!string} the formatted Date
   */
  formattedDate() {
    /* eslint-disable no-undef */
    return this.date.toLocaleString(navigator.language, {
      hour: '2-digit',
      minute: '2-digit',
      year: 'numeric',
      day: '2-digit',
      month: '2-digit',
      timeZoneName: 'short',
    });
    /* eslint-enable */
  }

  /**
   * For usage it is advisable to argument passed is older
   * time than the date created from new SaToolsDate(newerDate)
   * @param {!Date} compareToDate
   * @return {!string} formatted Date diff
   */
  formattedDateDiff(compareToDate = new Date()) {
    const timeDiff = this.date - compareToDate;

    if (timeDiff > 2 * 86_400_000) {
      return this.mediumDateFormat(compareToDate);
    } else if (timeDiff >= 86_400_000) {
      return 'Yesterday';
    } else if (timeDiff >= 3600_000) {
      return `${Math.round(timeDiff / 3600_000)} hour(s) ago`;
    }

    return `${Math.round(timeDiff / 60_000)} minute(s) ago`;
  }

  /**
   * Format date for a given date object into friendly
   * format like '12 minutes(s) ago' string.
   * @param {Date=} date the date from which to calculate diff.
   * @return {!string} formatted date after the diff logic.
   */
  formattedDateDiffFrom(date = new Date()) {
    return new SaToolsDate(date).formattedDateDiff(this.date);
  }

  /**
   * Format date for a given date-string into friendly
   * format like '12 minutes(s) ago' string.
   * @param {any} compareToDateStr
   * @return {!string}
   */
  formattedDateDiffStr(compareToDateStr) {
    const date = new Date(compareToDateStr);
    return this.formattedDateDiff(date);
  }

  /**
   * @param {!Date} dt
   * @return {!string}
   */
  mediumDateFormat(dt) {
    /* eslint-disable no-undef */
    return dt.toLocaleString(navigator.language, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
    /* eslint-enable */
  }
  /**
   * @param {!number} hours
   * @return {!Date}
   */
  subtractHours(hours) {
    return new Date(this.date - hours * 3_600_000);
  }

  /**
   * @param {!number} minutes
   * @return {!Date}
   */
  subtractMinutes(minutes) {
    return new Date(this.date - minutes * 60_000);
  }
}

export { SaToolsDate };
