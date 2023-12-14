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

/* eslint-disable react/prop-types */
import React, { useContext, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import TextField from '@mui/material/TextField';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import axios from 'axios';
import { checkAndExecuteFn } from './Common/CommonFunctions.jsx';
import { globalContext } from './PerfkitApp.jsx';
import { Box, Button, Typography } from '@mui/material';
import { JobResult } from './JobResult.jsx';

/**
 * Wrapper component that holds summary of the job's metrics result
 * @param {any} {onError}
 * @return {any}
 */
function JobDetails({ onError }) {
  const { jobId } = useParams();
  const [jobDetails, setJobDetails] = useState({});
  const { accessToken } = useContext(globalContext);

  useEffect(() => {
    if (!accessToken) {
      checkAndExecuteFn(onError, 'AccessToken Missing');
      return;
    }

    axios({
      method: 'get',
      url: `/benchmarkjobs/${jobId}`,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: 'application/json',
      },
    })
        .then((response) => response.data)
        .then((benchmarkJob) => {
          setJobDetails({ id: jobId, benchmarkJob: benchmarkJob });
        })
        .catch((error) => {
          if (onError && typeof onError == 'function') {
            onError(`Error Retrieving JobId:
              ${jobId}\n${JSON.stringify(error)}`);
          } else {
            /* eslint-disable no-undef */
            console.warn('JobDetails error', error);
            /* eslint-enable */
          }
        });
  }, [accessToken]);

  /* eslint-disable quote-props */
  return (
    jobDetails?.benchmarkJob && (
      <>
        <h2>Job Details</h2>
        <Box sx={{ display: 'flex' }}>
          <Box sx={{ minWidth: '300px' }}>
            <Typography>
              <b>Job Id:</b> {jobId}
            </Typography>
            <Typography>
              <b>Benchmark Type:</b>{' '}
              {jobDetails.benchmarkJob.jobInformation.type}
            </Typography>

            <RunInformationTable
              runInformation={
                jobDetails.benchmarkJob.runInformation
              }></RunInformationTable>
            <Button
              variant='contained'
              href={jobDetails.benchmarkJob.logUri}
              target='_blank'>
              Logs
            </Button>
          </Box>
          <TextField
            sx={{
              width: '60%',
              backgroundColor: 'white',

              'div:nth-child(2)': {
                padding: '10px 0px 0px 14px !important',
              },
              textarea: {
                height: '100%',
                overflow: 'auto!important',
              },
            }}
            aria-readonly={true}
            label='Configuration'
            variant='outlined'
            multiline
            value={jobDetails.benchmarkJob.jobInformation.benchmarkYaml}
            minRows={40}
          />
          <JobResult data={jobDetails.benchmarkJob.result?.metrics} />
        </Box>
      </>
    )
  );
}

/* eslint-disable comma-dangle, react/prop-types */
/**
 * Component that shows job's status and timestamp
 * @param {any} {runInformation}
 * @return {any}
 */
function RunInformationTable({ runInformation }) {
  return (
    <>
      <TableContainer
        style={{ width: '90%', marginRight: '20px', marginBottom: '20px' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Status</TableCell>
              <TableCell>Timestamp</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {runInformation &&
              runInformation
                  .sort(
                      (statusInfo1, statusInfo2) =>
                        new Date(statusInfo1.timestamp).valueOf() -
                        new Date(statusInfo2.timestamp).valueOf()
                  )
                  .map((statusInfo, index) => (
                    <TableRow key={`jobStatus-row-${index}`}>
                      <TableCell>{statusInfo.status}</TableCell>
                      <TableCell>{statusInfo.timestamp}</TableCell>
                    </TableRow>
                  ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}

export { JobDetails };
