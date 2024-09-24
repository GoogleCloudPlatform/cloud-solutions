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
import { TextField } from '@mui/material';
import { FC } from 'react';

const MIN_NODES = 1;
const MAX_NODES = 15000;

type Props = {
  minNodes: number;
  onChange: React.ChangeEventHandler<HTMLTextAreaElement | HTMLInputElement>;
};

const MinNumNodesField: FC<Props> = ({ minNodes, onChange }) => {
  return (
    <>
      <TextField
        label='Mininum number of nodes'
        variant='outlined'
        type='number'
        inputProps={{ min: MIN_NODES, max: MAX_NODES }}
        fullWidth
        required
        value={minNodes}
        onChange={onChange}
        sx={{ background: 'white' }}
      />
    </>
  );
};

export default MinNumNodesField;
