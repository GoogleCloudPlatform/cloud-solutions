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

import React, { useState, useEffect, createContext } from 'react';
import { Routes, Route, BrowserRouter } from 'react-router-dom';
import { LoadTestingJobs } from './Components/LoadTestingJobs';
import { ResponsiveAppBar } from
  './Components/ResponsiveAppBar/ResponsiveAppBar';
import { Snackbar, SnackbarContent } from '@mui/material';
import axios from 'axios';

const globalContext = createContext({ accessToken: null });

/**
 * Application container functional component
 * that holds routes for components
 * @return {!App}
 */
function App() {
  const [accessToken, setAccessToken] = useState(null);
  const [clientId, setClientId] = useState(null);
  const [errorContent, setErrorContent] = useState('');
  const [showError, setShowError] = useState(false);

  /**
   * Helper function to display Snackbar control with given error message.
   * @param {any} errorMessage
   */
  function showSnackbar(errorMessage) {
    setErrorContent(errorMessage);
    setShowError(true);
  }
  /* eslint-disable no-undef */
  useEffect(() => {
    axios(`/clientInfo`)
        .then((response) => setClientId(response.data))
        .catch((error) => console.log('clientInfo', error));
  }, []);
  /* eslint-enable */
  return (
    <globalContext.Provider value={{ accessToken: accessToken }}>
      <div className='App'>
        <ResponsiveAppBar
          toolName={'Performance Testing'}
          clientId={clientId}
          onSignIn={(idToken, userInfo, accessToken) => {
            setAccessToken(accessToken);
          }}
          onError={(err) => showSnackbar(JSON.stringify(err))}
        />
        <BrowserRouter>
          <Routes>
            <Route
              path='/webui'
              element={<LoadTestingJobs onError={showSnackbar} />}
            />
          </Routes>
        </BrowserRouter>
        <Snackbar
          open={showError}
          autoHideDuration={6000}
          onClose={() => setShowError(false)}>
          <SnackbarContent message={errorContent}></SnackbarContent>
        </Snackbar>
      </div>
    </globalContext.Provider>
  );
}

export { App, globalContext };
