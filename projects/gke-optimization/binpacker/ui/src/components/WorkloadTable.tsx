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
import MUIDataTable from 'mui-datatables';
import { Dispatch, FC, SetStateAction } from 'react';
import { Workload } from '../shared/types/types';
import LoadingOverlay from 'react-loading-overlay-ts';

const columnsWorkloads = [
  {
    name: 'name',
    label: 'Name',
    options: {
      filter: true,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'namespace',
    label: 'Namespace',
    options: {
      filter: true,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'replicas',
    label: 'Replicas',
    options: {
      filter: false,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'type',
    label: 'Type',
    options: {
      filter: true,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'cpuRequest',
    label: 'CPU Request',
    options: {
      filter: false,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'cpuLimit',
    label: 'CPU Limit',
    options: {
      filter: false,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'memoryRequestInMiB',
    label: 'Memory Request(MB)',
    options: {
      filter: false,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
  {
    name: 'memoryLimitInMiB',
    label: 'Memory Limit(MB)',
    options: {
      filter: false,
      sort: true,
      setCellHeaderProps: (value: object) => {
        return {
          style: {
            textAlign: 'left',
            marginLeft: '0',
            paddingLeft: '0',
          },
        };
      },
    },
  },
];

type Props = {
  workloads: Workload[];
  setCheckedIndexes: Dispatch<SetStateAction<number[]>>;
  checkedIndexes: number[];
  loading: boolean;
  loadingMessage: string;
};

const WorkloadTable: FC<Props> = ({
  workloads,
  setCheckedIndexes,
  checkedIndexes,
  loading,
  loadingMessage,
}) => {
  const optionsWorkloads = {
    filter: true,
    download: false,
    print: false,
    rowsSelected: checkedIndexes,
    customToolbarSelect: (): React.ReactNode => null,
    onRowSelectionChange: (
      currentRowsSelected: any[],
      allRowsSelected: any[],
      rowsSelected?: any[]
    ) => {
      if (rowsSelected == null) return;
      setCheckedIndexes(rowsSelected);
    },
  };

  return (
    <>
      <LoadingOverlay
        active={loading}
        spinner
        text={loadingMessage}>
        <MUIDataTable
          title={'Workloads'}
          data={workloads}
          columns={columnsWorkloads}
          options={optionsWorkloads}
        />
      </LoadingOverlay>
    </>
  );
};

export default WorkloadTable;
