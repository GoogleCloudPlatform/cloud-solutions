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

package com.google.cloud.solutions.trinoscaler.gcp;

import com.google.auth.oauth2.AccessToken;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.cloud.solutions.trinoscaler.Factory;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import java.io.IOException;

/**
 * Returns the default credentials available on the machine.
 *
 * <p>On Google Cloud Compute instances returns the instance's service account's credentials. When
 * running on a user machine please setup <a
 * href="https://cloud.google.com/docs/authentication/provide-credentials-adc">ADC</a>
 */
public class ApplicationDefaultCredentialProvider implements Factory<AccessToken> {
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  @Override
  public AccessToken create() {
    try {
      return GoogleCredentials.getApplicationDefault().getAccessToken();
    } catch (IOException ioException) {
      logger.atSevere().withCause(ioException).withStackTrace(StackSize.SMALL).log(
          "Error retrieving Application Default credentials");
    }

    return null;
  }
}
