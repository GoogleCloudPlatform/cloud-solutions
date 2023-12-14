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

type Props = {
  projectId: string;
  onChange: React.ChangeEventHandler<HTMLTextAreaElement | HTMLInputElement>;
  editable: boolean;
};

const ProjectIdField: FC<Props> = ({ projectId, onChange, editable }) => {
  return (
    <>
      <TextField
        label='Project ID'
        variant='outlined'
        fullWidth
        required
        value={projectId}
        sx={{ background: 'white' }}
        onChange={onChange}
        disabled={!editable}
      />
    </>
  );
};

export default ProjectIdField;
