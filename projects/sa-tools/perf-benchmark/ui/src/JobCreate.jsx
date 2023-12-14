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

/* eslint-disable react/prop-types, quote-props */
import React, { useContext, useRef, useState } from 'react';
import TextareaAutosize from '@mui/base/TextareaAutosize';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import Select from '@mui/material/Select';
import { useNavigate } from 'react-router-dom';
import Config from './perfkit_config.json';
import axios from 'axios';
import { checkAndExecuteFn } from './Common/CommonFunctions.jsx';
import { globalContext } from './PerfkitApp.jsx';
import { Box, Typography } from '@mui/material';
import './Common/css/satools.scss';

/**
 * Component/forms to create a new perfkit job.
 * @param {any} onError
 * @param {any} onCreating
 * @param {any} onClose
 * @return {any}
 */
function JobCreate({ onError, onCreating, onClose }) {
  const [benchmarkType, setBenchmarkType] = useState('SELECT');
  const [benchmarkYaml, setBenchmarkYaml] = useState('');
  const { accessToken } = useContext(globalContext);

  const configYamlRef = useRef();
  const navigate = useNavigate();

  const createJobFn = () => {
    if (!accessToken) {
      checkAndExecuteFn(onError, 'AccessToken Missing');
      return;
    }
    checkAndExecuteFn(onCreating);
    axios
        .post(
            `/benchmarkjobs`,
            /* requestBody= */
            {
              type: benchmarkType.toUpperCase(),
              benchmarkYaml: benchmarkYaml,
            },
            /* options= */
            {
              headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
              },
            },
        )
        .then((response) => response.data)
        .then((benchmarkJobDetails) =>
          /* eslint-disable comma-dangle */
          navigate(`/jobs/${benchmarkJobDetails.id}`)
          /* eslint-enable */
        )
        // Show the error in a snackbar
        .catch((error) => {
          if (onError && typeof onError == 'function') {
            onError(`Error Creating Job: ${JSON.stringify(error)}`);
          } else {
            /* eslint-disable no-undef */
            console.warn('createJobError', error);
            /* eslint-enable */
          }
        });
  };

  return (
    <>
      <Box sx={{ margin: '1rem', width: '500px' }}>
        <Typography
          variant='h6'
          component='h2'
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            marginBottom: '15px',
          }}>
          <span
            onClick={() => checkAndExecuteFn(onClose)}
            style={{ cursor: 'pointer' }}
            className='google-symbols'>
            close
          </span>
        </Typography>
        <h2>Create Job</h2>

        <InputLabel id='benchmark-type-label'>Benchmark</InputLabel>
        <Select
          labelId='benchmark-type-label'
          style={{ width: '300px' }}
          value={benchmarkType}
          onChange={(event, child) => {
            setBenchmarkType(child.props.value);
            axios
                .get(`/custom_benchmark/${child.props.value.toLowerCase()}.yml`)
                .then((resp) => setBenchmarkYaml(resp.data));
          }}>
          <MenuItem
            key={'SELECT'}
            value={'SELECT'}>
            <em>PLEASE SELECT</em>
          </MenuItem>
          {Config.benchmarks.map((benchmarkName, index) => (
            <MenuItem
              value={benchmarkName}
              key={index}>
              {benchmarkName}
            </MenuItem>
          ))}
        </Select>
        <Box
          style={{
            display: 'flex',
            flexDirection: 'column',
            marginTop: '1rem',
          }}>
          <InputLabel>Configuration YAML</InputLabel>
          <TextareaAutosize
            ref={configYamlRef}
            defaultValue={benchmarkYaml}
            onBlurCapture={() => setBenchmarkYaml(configYamlRef.current.value)}
            minRows={30}
            style={{ maxWidth: '500px' }}
          />
          <br />
          <Button
            variant='contained'
            sx={{ width: '100px' }}
            onClick={() => {
              if (benchmarkYaml !== '' && benchmarkType !== '') {
                createJobFn();
              }
            }}>
            Create
          </Button>
        </Box>
      </Box>
    </>
  );
}

export { JobCreate };
