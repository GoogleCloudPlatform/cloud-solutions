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
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
} from '@mui/material';
import { FC } from 'react';
import { Cluster } from '../../proto/metric.pb';

type Props = {
  cluster: Cluster | null;
  clusters: Cluster[];
  selectable: boolean;
  onChange: (event: SelectChangeEvent<Cluster>) => void;
};

const buildClusterSelection = (cluster: Cluster): string => {
  return `${cluster.name} (${cluster.numberOfNodes} nodes, ${cluster.totalCpu} vCPU, ${cluster.totalMemoryInGib} GB RAM)`;
};

const ClusterSelector: FC<Props> = ({
  cluster,
  clusters,
  selectable,
  onChange,
}) => {
  return (
    <>
      <FormControl
        fullWidth
        // disabled={calculating}
      >
        <InputLabel id='cluster-label'>Cluster</InputLabel>
        <Select
          id='cluster-select'
          labelId='cluster-label'
          label='Cluster'
          value={cluster as any}
          onChange={onChange}
          disabled={!selectable}>
          {clusters.map((value, index) => (
            <MenuItem
              value={value as any}
              key={index}>
              {buildClusterSelection(value)}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </>
  );
};

export default ClusterSelector;
