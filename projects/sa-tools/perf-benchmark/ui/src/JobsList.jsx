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

import React, { useContext, useEffect, useState } from 'react';
import Button from '@mui/material/Button';
import { useNavigate } from 'react-router-dom';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import axios from 'axios';

import { checkAndExecuteFn } from './Common/CommonFunctions.jsx';
import { globalContext } from './PerfkitApp.jsx';
import { Backdrop, CircularProgress, Drawer, Link, Paper } from '@mui/material';
import { JobCreate } from './JobCreate.jsx';

/* eslint-disable react/prop-types */
/**
 * Component to display list of jobs in table
 * @param {any} {onError}
 * @return {any}
 */
function JobsList({ onError }) {
  const navigate = useNavigate();
  const [jobsList, setJobsList] = useState([]);
  const { accessToken } = useContext(globalContext);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      checkAndExecuteFn(onError, 'AccessToken Missing');
      return;
    }
    setLoading(true);
    axios
        .get(`/benchmarkjobs`, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        })
        .then((response) => response.data)
        .then((jobsListData) => {
          setLoading(false);
          setJobsList(jobsListData.jobs);
        });
  }, [accessToken]);

  const LoadingBackdrop = (
    <Backdrop
      sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
      open={loading}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
        }}>
        <CircularProgress color='inherit' />
        <span style={{ marginTop: 5 }}>Loading...</span>
      </div>
    </Backdrop>
  );

  return (
    <>
      <Button
        variant={'contained'}
        onClick={() => setDrawerOpen(true)}>
        Create
      </Button>
      {LoadingBackdrop}
      {!loading && (jobsList == null || jobsList.length === 0) && (
        <h3>No Jobs</h3>
      )}
      {!loading && jobsList && jobsList.length > 0 && (
        <TableContainer
          component={Paper}
          sx={{ marginTop: '1rem' }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Job Id</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Benchmark Type</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {jobsList.map((job) => (
                <TableRow key={`jobsList-${job.id}`}>
                  <TableCell>
                    <Link
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/jobs/${job.id}`)}>
                      {job.id}
                    </Link>
                  </TableCell>
                  <TableCell>{latestJobStatus(job)}</TableCell>
                  <TableCell>{job.jobInformation.type}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <Drawer
        anchor={'right'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}>
        <JobCreate
          onCreating={() => setLoading(true)}
          onError={(msg) => {
            onError(msg);
            setLoading(false);
          }}
          onClose={() => setDrawerOpen(false)}
        />
      </Drawer>
    </>
  );
}

/* eslint-disable comma-dangle */
/**
 * Get the latest job's status from job's status histories
 * @param {any} job
 * @return {any}
 */
function latestJobStatus(job) {
  return job.runInformation.sort(
      (statusInfo1, statusInfo2) =>
        new Date(statusInfo2.timestamp).valueOf() -
        new Date(statusInfo1.timestamp).valueOf()
  )[0].status;
}
/* eslint-enable */

export { JobsList };
