/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { Alert, AlertTitle } from '@mui/material';
import { Zoom, toast } from 'react-toastify';

export type ErrorResponse = {
  message: string;
  details: string;
};

const AUTOCLOSE_MS = 6000;

export const notifySuccess = (message: string) => {
  toast(
    <Alert
      severity='success'
      sx={{ width: '100%' }}>
      <AlertTitle sx={{ my: 0 }}>{message}</AlertTitle>
    </Alert>,
    {
      position: 'top-right',
      autoClose: AUTOCLOSE_MS,
      hideProgressBar: true,
      closeOnClick: true,
      pauseOnHover: true,
      draggable: true,
      progress: undefined,
      theme: 'light',
      transition: Zoom,
    }
  );
};

export const notifyError = (error: ErrorResponse) =>
  toast(
    <Alert
      severity='error'
      sx={{ width: '100%' }}>
      <AlertTitle sx={{ my: 0 }}>{error.message}</AlertTitle>
      {error.details}
    </Alert>,
    {
      position: 'top-right',
      autoClose: AUTOCLOSE_MS,
      hideProgressBar: true,
      closeOnClick: true,
      pauseOnHover: true,
      draggable: true,
      progress: undefined,
      theme: 'light',
      transition: Zoom,
    }
  );
