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
import { PodExtended } from '../shared/types/types';
import LoadingOverlay from 'react-loading-overlay-ts';

const columnsPods = [
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
      setCellProps: () => ({ style: { whiteSpace: 'pre' } }),
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
    name: 'status',
    label: 'Status',
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
    name: 'parent',
    label: 'Parent',
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
  pods: PodExtended[];
  setCheckedIndexes: Dispatch<SetStateAction<number[]>>;
  checkedIndexes: number[];
  loading: boolean;
  loadingMessage: string;
};

const PodTable: FC<Props> = ({
  pods,
  setCheckedIndexes,
  checkedIndexes,
  loading,
  loadingMessage,
}) => {
  const optionsPods = {
    filter: true,
    download: false,
    print: false,
    rowsSelected: checkedIndexes,
    onRowSelectionChange: (
      currentRowsSelected: any[],
      allRowsSelected: any[],
      rowsSelected?: any[]
    ) => {
      if (rowsSelected == null) return;
      setCheckedIndexes(rowsSelected);
    },
    customToolbarSelect: (): React.ReactNode => null,
  };

  return (
    <>
      <LoadingOverlay
        active={loading}
        spinner
        text={loadingMessage}>
        <MUIDataTable
          title={'Pods'}
          data={pods}
          columns={columnsPods}
          options={optionsPods}
        />
      </LoadingOverlay>
    </>
  );
};

export default PodTable;
