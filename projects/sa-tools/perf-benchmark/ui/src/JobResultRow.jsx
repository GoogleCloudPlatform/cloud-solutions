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
import { Link, TableCell, TableRow } from '@mui/material';
import { SaToolsDate } from './Common/SaToolsDate';

/**
 * Component of individual job row
 * @param {any} metric
 * @param {any} onMetricClick
 * @return {any}
 */
function JobResultRow({ metric, onMetricClick }) {
  const prettifyLabels = (labels) => labels.join('\n');
  return (
    <TableRow sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
      <TableCell
        align='left'
        component='th'
        scope='row'>
        {metric.metric}
      </TableCell>
      <TableCell align='right'>{metric.value}</TableCell>
      <TableCell align='right'>
        {new SaToolsDate(metric.timestamp).formattedDate()}
      </TableCell>
      <TableCell align='right'>
        <Link
          sx={{ cursor: 'pointer' }}
          onClick={(e) =>
            onMetricClick(e, 'left', prettifyLabels(metric.labels))
          }>
          {metric.labels[0]} ...
        </Link>
      </TableCell>
    </TableRow>
  );
}

export { JobResultRow };
