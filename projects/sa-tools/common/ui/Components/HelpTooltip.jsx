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
import { Popover, Typography } from '@mui/material';
import { useRef, useState } from 'react';
import '../css/satools.scss';
import ReactMarkdown from 'react-markdown';

function HelpTooltip({ attribute }) {
  const helpIconRef = useRef();
  const [popover, setPopOver] = useState(false);

  return (
    <>
      <span
        ref={helpIconRef}
        onClick={() => setPopOver(true)}
        style={{ cursor: 'pointer', marginLeft: '5px' }}
        className='google-symbols google-symbols-filled'>
        help
      </span>
      <Popover
        open={popover}
        anchorEl={helpIconRef.current}
        onClose={() => setPopOver(false)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}>
        <Typography style={{ padding: 5 }}>
          <ReactMarkdown>{attribute.helpText ?? attribute.id}</ReactMarkdown>
        </Typography>
      </Popover>
    </>
  );
}

export { HelpTooltip };
