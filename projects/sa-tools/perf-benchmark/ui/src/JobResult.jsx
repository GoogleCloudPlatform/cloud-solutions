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
import React from 'react';
import {
  Paper,
  Popover,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { JobResultRow } from './JobResultRow';

/**
 * JobResult component for Job's metrics display
 * @param {any} {data}
 * @return {any}
 */
function JobResult({ data }) {
  const [anchorEl, setAnchorEl] = useState(null);
  const [openPopper, setOpenPopper] = useState(false);
  const [popperContent, setPopperContent] = useState('');

  const handleClick = (event, newPlacement, content) => {
    setAnchorEl(event.currentTarget);
    setOpenPopper(true);
    setPopperContent(content);
  };

  const handlePopupClose = () => {
    setOpenPopper(false);
    setAnchorEl(null);
  };

  if (!data) {
    return (
      <p style={{ marginLeft: '15px' }}>
        No Metrics Result Avalable Yet. Please Refresh this page after 5-10
        mins.
      </p>
    );
  }

  return (
    <>
      <TableContainer
        component={Paper}
        sx={{ marginLeft: '15px', height: '99%' }}>
        <Table aria-label='simple table'>
          <TableHead>
            <TableRow sx={{ backgroundColor: '#eaeaea' }}>
              <TableCell align='left'>Metric Name</TableCell>
              <TableCell align='right'>Value</TableCell>
              <TableCell align='right'>Timestamp</TableCell>
              <TableCell align='right'>Value Labels</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.map((result, index) => (
              <JobResultRow
                key={`benchmark-${index}`}
                metric={result}
                onMetricClick={handleClick}
              />
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Popover
        open={openPopper}
        anchorEl={anchorEl}
        onClose={handlePopupClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}>
        <Typography
          sx={{
            p: 2,
            fontFamily: 'Roboto Condensed',
            fontSize: '1rem!important',
            whiteSpace: 'pre-line',
          }}>
          {popperContent}
        </Typography>
      </Popover>
    </>
  );
}
export { JobResult };
