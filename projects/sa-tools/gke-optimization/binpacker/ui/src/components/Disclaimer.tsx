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
import { Typography } from '@mui/material';
import { FC } from 'react';

const Disclaimer: FC = () => {
  return (
    <>
      <Typography
        sx={{
          fontStyle: 'italic',
        }}
        textAlign={'left'}>
        BinPacking Recommendation tool is the theoretical minima calculated
        based on{' '}
        <a
          href='https://en.wikipedia.org/wiki/First-fit-decreasing_bin_packing'
          target='_blank'
          rel='noreferrer'>
          First-fit-decreasing algorithm
        </a>
        . It is a mathematical estimation and may differ from how Kubernetes
        Scheduler might choose to pack the pod (
        <a
          href='https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/'
          target='_blank'
          rel='noreferrer'>
          read more here
        </a>
        ). Please test your workloads thoroughly with the new config before
        deploying in production.
      </Typography>
    </>
  );
};

export default Disclaimer;
