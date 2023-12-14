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

import { CircularProgress, Link, TableCell, TableRow } from '@mui/material';
import React from 'react';
import { SaToolsDate } from '../utils/SaToolsDate';
import './LoadTestingJob.scss';
import { convertProvisionStatus, convertTaskStatus } from '../utils/common';

/* eslint-disable react/prop-types */
/**
 * Individual (a row of) Performance Testing's Job Component
 * @param {any} correlation_id:correlationId
 * @param {any} download_link:downloadLink
 * @param {any} created
 * @param {any} provision_status:provisionStatus=0
 * @param {any} task_status:taskStatus
 * @param {any} logs_link:logsLink
 * @param {any} metrics_link:metricsLink
 * @param {any} onIdClicked
 * @return {any}
 */
function LoadTestingJob({
  correlation_id: correlationId,
  download_link: downloadLink,
  created,
  provision_status: provisionStatus = 0,
  task_status: taskStatus,
  logs_link: logsLink,
  metrics_link: metricsLink,
  onIdClicked,
}) {
  return (
    <>
      <TableRow sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
        <TableCell
          align='left'
          component='th'
          scope='row'>
          <Link
            onClick={() => onIdClicked(correlationId)}
            sx={{ cursor: 'pointer' }}>
            {correlationId}
          </Link>
        </TableCell>
        <TableCell align='left'>
          {SaToolsDate.fromUnixSeconds(created.seconds).formattedDateDiffFrom()}
        </TableCell>
        <TableCell align='left'>
          {convertProvisionStatus(provisionStatus)}
        </TableCell>
        <TableCell align='left'>{convertTaskStatus(taskStatus)}</TableCell>
        <TableCell align='left'>
          {logsLink ? (
            <Link
              href={logsLink}
              target='_blank'
              sx={{ cursor: 'pointer' }}>
              View Logs
            </Link>
          ) : (
            <CircularProgress
              color='primary'
              size={20}
            />
          )}
        </TableCell>
        <TableCell align='left'>
          {metricsLink ? (
            <Link
              href={metricsLink}
              target='_blank'
              sx={{ cursor: 'pointer' }}>
              View Monitoring
            </Link>
          ) : (
            <CircularProgress
              color='primary'
              size={20}
            />
          )}
        </TableCell>
      </TableRow>
    </>
  );
}

export { LoadTestingJob };
