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

import axios from 'axios';
import React, { useState, useEffect, createContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Snackbar from '@mui/material/Snackbar';
import SnackbarContent from '@mui/material/SnackbarContent';
import { JobDetails } from './JobDetails.jsx';
import { JobsList } from './JobsList.jsx';
import { ResponsiveAppBar } from './Common/ResponsiveAppBar/ResponsiveAppBar';
import { Box } from '@mui/material';

const globalContext = createContext({ accessToken: null });

/**
 * Application container functional component
 * that holds routes for components
 * @return {!App}
 */
function PerfkitApp() {
  const [showError, setShowError] = useState(false);
  const [errorContent, setErrorContent] = useState('');
  const [clientId, setClientId] = useState(null);
  const [accessToken, setAccessToken] = useState(null);

  /**
  * Helper function to show error message.
  * @param {any} errorMessage
  */
  function showSnackbar(errorMessage) {
    setErrorContent(errorMessage);
    setShowError(true);
  }
  /* eslint-disable no-undef */
  useEffect(() => {
    axios(`/clientInfo`)
        .then((response) => setClientId(response.data['clientId']))
        .catch((error) => console.log('clientInfo', error));
  }, []);
  /* eslint-enable */

  return (
    <globalContext.Provider value={{ accessToken: accessToken }}>
      <ResponsiveAppBar
        toolName={'Perfkit Benchmarking'}
        clientId={clientId}
        onSignIn={(idToken, userInfo, accessToken) => {
          setAccessToken(accessToken);
        }}
        onError={(err) => showSnackbar(JSON.stringify(err))}
      />
      <Box sx={{ margin: '20px' }}>
        <BrowserRouter>
          <Routes>
            <Route
              path={'/'}
              element={
                <Navigate
                  replace
                  to='/jobs'
                />
              }
            />
            <Route
              path={'/jobs'}
              element={<JobsList onError={showSnackbar} />}
            />
            <Route
              path={'/jobs/:jobId'}
              element={<JobDetails onError={showSnackbar} />}
            />
          </Routes>
        </BrowserRouter>
      </Box>
      <Snackbar
        open={showError}
        autoHideDuration={6000}
        onClose={() => setShowError(false)}>
        <SnackbarContent message={errorContent}></SnackbarContent>
      </Snackbar>
    </globalContext.Provider>
  );
}

export { PerfkitApp, globalContext };
