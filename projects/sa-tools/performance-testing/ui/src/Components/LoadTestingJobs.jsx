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

import React from 'react';
import {
  Backdrop,
  Box,
  Button,
  CircularProgress,
  Drawer,
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
} from '@mui/material';
import axios from 'axios';
import { useEffect, useMemo, useState } from 'react';
import { CreateOrViewLoadTestingJob } from './CreateOrViewLoadTestingJob';
import { LoadTestingJob } from './LoadTestingJob';

// const BACKEND_HOST = import.meta.env.VITE_BACKEND_HOST ?? '';

/**
 * LoadTestingJobs component that displays list of all PT jobs.
 * @return {any}
 */
function LoadTestingJobs() {
  const [jobs, setJobs] = useState([]);
  const [pageLoading, setPageLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeComponentId, setActiveComponentId] = useState(null);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPageLoading(true);
    axios
        .get(`/v2/pttask` /* options=*/, {
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        })
        .then((resp) => {
          if (resp.data) {
            const sortedJobs = resp.data
                .filter((job) => Object.keys(job).length > 0)
                .sort(
                    /* descending */
                    (a, b) => b.created.seconds - a.created.seconds,
                );
            setJobs(sortedJobs);
          }
        })
        /* eslint-disable */
        .catch((error) => console.log(error))
        /* eslint-enable */
        .finally(() => setPageLoading(false));
  }, []);

  const handleCreateTestClick = () => {
    setActiveComponentId('');
    setDrawerOpen(true);
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const visibleRows = useMemo(
      () => jobs.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
      [page, rowsPerPage, jobs],
  );

  const LoadingBackdrop = (
    <Backdrop
      sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
      open={pageLoading}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
        }}>
        <CircularProgress color='inherit' />
        <span style={{ marginTop: 5 }}>Loading ...</span>
      </div>
    </Backdrop>
  );

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          columnGap: '10px',
          margin: '0 10px',
        }}>
        <Button
          variant='contained'
          sx={{ marginTop: '20px', justifyContent: 'space-between' }}
          onClick={handleCreateTestClick}>
          <span>Create Test</span>
        </Button>
        <Button
          variant='contained'
          sx={{ marginTop: '20px', justifyContent: 'space-between' }}
          onClick={() => {
            /* eslint-disable */
            window.location.href = '/webui';
            /* eslint-enable */
          }}>
          <span>Refresh Page</span>
        </Button>
      </div>
      {LoadingBackdrop}

      <Box sx={{ width: '60%', margin: 'auto', marginTop: '20px' }}>
        <p>
          <i>Refresh the page for the latest statuses</i>
        </p>
        <TableContainer component={Paper}>
          <Table
            sx={{ Width: 650 }}
            aria-label='simple table'>
            <TableHead>
              <TableRow sx={{ backgroundColor: '#eaeaea' }}>
                <TableCell align='left'>Test ID</TableCell>
                <TableCell align='left'>Created</TableCell>
                <TableCell align='left'>Provisioning Status</TableCell>
                <TableCell align='left'>Test Status</TableCell>
                <TableCell align='left'>Logs</TableCell>
                <TableCell align='left'>Monitoring</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleRows &&
                visibleRows.length > 0 &&
                visibleRows.map((job, index) => (
                  <LoadTestingJob
                    key={`job-${index}`}
                    {...job}
                    onIdClicked={(correlationId) => {
                      setActiveComponentId(correlationId);
                      setDrawerOpen(true);
                    }}
                  />
                ))}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component='div'
          count={jobs.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
        {pageLoading && (
          <Box sx={{ width: '100%' }}>
            <LinearProgress />
          </Box>
        )}
        <Drawer
          anchor={'right'}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}>
          <CreateOrViewLoadTestingJob
            correlationId={activeComponentId}
            createMode={activeComponentId ? false : true}
            onClose={() => setDrawerOpen(false)}
          />
        </Drawer>
      </Box>
    </>
  );
}

export { LoadTestingJobs };
