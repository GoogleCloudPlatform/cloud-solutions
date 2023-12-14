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
import { Button } from '@mui/material';
import { FC } from 'react';

type Props = {
  clickable: boolean;
  onClick: (event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
};

const DiscoverButton: FC<Props> = ({ clickable, onClick }) => {
  return (
    <>
      <Button
        onClick={onClick}
        fullWidth
        disabled={!clickable}
        variant='contained'
        sx={{ height: 56 }}>
        Discover
      </Button>
    </>
  );
};

export default DiscoverButton;
