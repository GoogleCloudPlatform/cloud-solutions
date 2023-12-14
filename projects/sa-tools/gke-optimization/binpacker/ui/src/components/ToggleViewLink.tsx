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
import { Link, Typography } from '@mui/material';
import { FC } from 'react';

type Props = {
  showWorkloadsView: boolean;
  onClick: (event: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => void;
  clickable: boolean;
};

const ToggleViewLink: FC<Props> = ({
  showWorkloadsView,
  onClick,
  clickable,
}) => {
  return (
    <>
      <Typography align='center'>
        <Link
          component='button'
          sx={{ height: 56, fontSize: 16 }}
          onClick={onClick}
          disabled={!clickable}>
          {showWorkloadsView
            ? 'Switch to Pods view'
            : 'Switch to Workloads view'}
        </Link>
      </Typography>
    </>
  );
};

export default ToggleViewLink;
