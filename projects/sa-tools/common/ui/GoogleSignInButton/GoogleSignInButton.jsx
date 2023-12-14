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

import React, { useEffect, useRef, useState } from 'react';
import * as jose from 'jose';
import { checkAndExecuteFn } from '../CommonFunctions';
import { StringSet } from '../StringSet';

/* global google */

const FIXED_SCOPES = [
  'https://www.googleapis.com/auth/userinfo.email',
  'openid',
  'https://www.googleapis.com/auth/userinfo.profile',
];
/**
 * Provides a simple Google Identity SignIn Component
 *
 * Setup:
 * (1) Follow the steps as per https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
 * to generate a client-id
 *
 * (2) Ensure that you add following script tag to the index.html
 * <script src="https://accounts.google.com/gsi/client"></script>
 *
 * Pass the OAuth Scopes if you want to specify them.
 * The component will automatically add following scopes
 *  (1) https://www.googleapis.com/auth/userinfo.email
 *  (2) openid
 *  (3) https://www.googleapis.com/auth/userinfo.profile
 *
 * @param {!string} clientId the OAuth client Id created during Setup Step#1
 * @param {boolean=} [enableOneTap=true] enable/disable OnTap Sign-In experience
 * @param {string[]=} [scopes=] the OAuth scopes to request for user permissions
 * @param {?function} onSignIn optional component to receive sign-in information
 * @param {?function} onError optional function to receive error messages.
 * @return {JSX.Element}
 * @constructor
 */
function GoogleSignInButton({
  enableOneTap = true,
  scopes = ['https://www.googleapis.com/auth/cloud-platform'],
  clientId,
  onSignIn,
  onError,
}) {
  const [auth, setAuth] = useState(false);
  const [userInfo, setUserInfo] = useState({});
  const googleSignInRef = useRef();

  const handleSignIn = (signInEvent) => {
    const idToken = signInEvent['credential'];
    const decodedUserInfo = jose.decodeJwt(idToken);

    const tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: new StringSet(FIXED_SCOPES).addAll(scopes).toArray().join(' '),
      hint: decodedUserInfo['email'],
      prompt: '',
      error_callback: (err) => checkAndExecuteFn(onError, err),
      callback: (tokenResponse) => {
        setUserInfo(decodedUserInfo);
        setAuth(true);
        checkAndExecuteFn(
          onSignIn,
          idToken,
          decodedUserInfo,
          tokenResponse['access_token']
        );
      },
    });

    tokenClient.requestAccessToken();
  };

  useEffect(() => {
    google.accounts.id.initialize({
      client_id: clientId,
      context: 'use',
      auto_select: true,
      cancel_on_tap_outside: false,
      prompt_parent_id: googleSignInRef.current,
      callback: handleSignIn,
    });
    google.accounts.id.renderButton(googleSignInRef.current, {
      theme: 'outline',
      type: 'standard',
      text: '',
      size: 'large',
      shape: 'pill',
    });

    enableOneTap && google.accounts.id.prompt();
  }, []);

  return (
    <>
      {!auth && <div ref={googleSignInRef} />}
      {auth && (
        <img
          src={userInfo['picture']}
          style={{ width: '2.5rem', borderRadius: '50%' }}
        />
      )}
    </>
  );
}

export { GoogleSignInButton };
