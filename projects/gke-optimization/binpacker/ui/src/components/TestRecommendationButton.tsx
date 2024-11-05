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

const URL = 'https://google.com/';

const TestRecommendationButton: FC = () => {
  const onClickTestRecommendations = () => {
    window.open(URL, '_blank', 'noreferrer');
  };
  return (
    <>
      <Button
        sx={{ height: 56, mt: 2 }}
        variant='contained'
        disabled={true}
        onClick={onClickTestRecommendations}
        fullWidth>
        Test Recommendations
      </Button>
    </>
  );
};

export default TestRecommendationButton;
