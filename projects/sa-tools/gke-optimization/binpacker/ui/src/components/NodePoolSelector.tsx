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
  Checkbox,
  FormControl,
  InputLabel,
  ListItemText,
  MenuItem,
  OutlinedInput,
  Select,
  SelectChangeEvent,
} from '@mui/material';
import { FC } from 'react';
import { Nodepool } from '../../proto/metric.pb';

type Props = {
  nodePools: Nodepool[];
  selectedNodePools: Nodepool[];
  selectable: boolean;
  onChange: (event: SelectChangeEvent<Nodepool[]>) => void;
};

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
export const UNSCHEDULED_LABEL = 'Unscheduled';

export const UNSCHEDULED_NODEPOOL: Nodepool = {
  name: UNSCHEDULED_LABEL,
  cluster: '',
  clusterLocation: '',
  machineType: '',
  cpu: 0,
  memoryInGib: 0,
  numberOfNodes: 0,
  totalCpu: 0,
  totalMemoryInGib: 0,
};

const MenuProps = {
  PaperProps: {
    style: {
      maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
      width: 250,
    },
  },
};

const buildNodePoolSelection = (nodePool: Nodepool): string => {
  if (nodePool.name === UNSCHEDULED_LABEL) return UNSCHEDULED_LABEL;
  return `${nodePool.name} (${nodePool.machineType} * ${nodePool.numberOfNodes}, ${nodePool.totalCpu} vCPU, ${nodePool.totalMemoryInGib} GB RAM)`;
};

const NodePoolSelector: FC<Props> = ({
  nodePools,
  selectedNodePools,
  selectable,
  onChange,
}) => {
  return (
    <>
      <FormControl
        fullWidth
        // disabled={calculating}
      >
        <InputLabel id='nodepool-label'>Node Pool</InputLabel>
        <Select
          id='nodepool-select'
          labelId='nodepool-label'
          label='Node Pool'
          disabled={!selectable}
          multiple
          MenuProps={MenuProps}
          value={selectedNodePools}
          onChange={onChange}
          input={<OutlinedInput label='Node Pool' />}
          renderValue={(selected) => {
            const selectedNames = selected.map((item) => item.name);
            const filteredNodePoolsForRender = nodePools.filter((item) => {
              return selectedNames.includes(item.name);
            });
            return filteredNodePoolsForRender
              .map((item) => item.name)
              .join(', ');
          }}>
          {nodePools.map((value, index) => (
            <MenuItem
              value={value as any}
              key={index}>
              <Checkbox
                checked={
                  selectedNodePools
                    .map((item) => item.name)
                    .indexOf(value.name) > -1
                }
              />
              <ListItemText primary={buildNodePoolSelection(value)} />
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </>
  );
};

export default NodePoolSelector;
