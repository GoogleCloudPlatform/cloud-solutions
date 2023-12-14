/*
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* eslint-disable react/prop-types */
import React from 'react';
import {
  Backdrop,
  Box,
  Button,
  CircularProgress,
  TextField,
  Typography,
} from '@mui/material';
import axios from 'axios';
import { useContext, useEffect, useState } from 'react';
import { globalContext } from '../App';
import {
  AttributeData,
  AttributeValue,
  convertArrayToMap,
} from '../utils/CommonFunctions';
import {
  convertTaskStatus,
  convertTaskType,
  createRequestBody,
} from '../utils/common';
import { AttributeField } from './AttributeInputFields/AttributeField';
import { DropdownInput } from './AttributeInputFields/DropdownInput';
import { RepeatedField } from './AttributeInputFields/RepeatedField';
import { CustomSnackbar } from './Snackbar';

/** UI structures for the form with empty value attributes */
const loadTestingJobAttributeData = {
  nestedAttributes: [
    new AttributeData(
        {
          required: true,
          displayName: 'Target URL',
          id: 'targetUrl',
          type: 'STRING',
          defaultVisible: true,
          helpText: 'The URL of targeting website, eg: http://blazedemo.com',
          exampleInputText: 'http://blazedemo.com',
        },
        new AttributeValue(''),
    ),
    new AttributeData(
        {
          required: true,
          displayName: 'Virtual Users',
          id: 'totalUsers',
          type: 'NUMBER',
          defaultVisible: true,
          helpText: 'How many users will be simulated',
          exampleInputText: 1000,
        },
        new AttributeValue(''),
    ),
    new AttributeData(
        {
          required: true,
          displayName: 'Duration',
          id: 'duration',
          type: 'NUMBER',
          defaultVisible: true,
          helpText: 'How long the test will run, unit is minute',
          exampleInputText: 5,
        },
        new AttributeValue(''),
    ),
    new AttributeData(
        {
          required: true,
          displayName: 'Ramp Up',
          id: 'rampUp',
          type: 'STRING',
          defaultVisible: true,
          helpText: 'Ramp-up time to reach simulated, unit is minute',
          exampleInputText: 5,
        },
        new AttributeValue(''),
    ),
    new AttributeData(
        {
          required: true,
          displayName: 'Number of Workers',
          id: 'workers',
          type: 'NUMBER',
          defaultVisible: true,
          helpText: `The number of worker to run the test, eg: 10.
          In distribution mode that is calculated by
          virtualUsers x precentageOfTraffic,
          but in local mode, the number could be define by user`,
          exampleInputText: 1,
        },
        new AttributeValue(''),
    ),
  ],
};

/** UI structures for each dropdown's fields */
const attributeGroups = [
  {
    id: 'LOCAL',
    repeated: false,
    defaultVisible: true,
    required: true,
    displayName: 'LOCAL',
    helpText: 'Local mode of performance load testing',
    type: 'OBJECT',
    nestedAttributes: [
      {
        displayName: '# of Workers',
        id: 'workers',
        type: 'NUMBER',
        defaultVisible: true,
        exampleInputText: 2,
        helpText: `Round Up the value of Virtual Users / 1000.
          This value will be overriden based on the Virtual Users count`,
      },
    ],
  },
  {
    id: 'LOAD DISTRIBUTION',
    repeated: false,
    defaultVisible: true,
    required: true,
    displayName: 'LOAD DISTRIBUTION',
    helpText: 'Load distribution mode of performance load testing',
    type: 'OBJECT',
    nestedAttributes: [
      {
        displayName: 'Region',
        id: 'region',
        type: 'STRING',
        defaultVisible: true,
        helpText: 'GCP region, eg: us-central1',
        exampleInputText: 'us-central1',
      },
      {
        displayName: '% of Traffic',
        id: 'percent',
        type: 'STRING',
        defaultVisible: true,
        helpText: `How many percent of traffic will be sent to the target
          website. In integer.`,
        exampleInputText: 90,
      },
      {
        displayName: '# of Workers',
        id: 'workers',
        type: 'NUMBER',
        defaultVisible: true,
        exampleInputText: '1',
        helpText: `The number of worker to run the test, eg: 10. 
          In distribution mode that is calculated by 
          virtualUsers x precentageOfTraffic, but in local mode, 
          the number could be define by user`,
      },
    ],
  },
];

/**
 * Create Load Testing Job Component
 * @param {any} {createMode
 * @param {any} correlationId
 * @param {any} onClose}
 * @return {any}
 */
function CreateOrViewLoadTestingJob({ createMode, correlationId, onClose }) {
  const [selectedTaskType, setSelectedTaskType] = useState(null);
  const [selectedAttributeGroup, setSelectedAttributeGroup] = useState(null);
  const [model, setModel] = useState(loadTestingJobAttributeData);
  /* eslint-disable no-unused-vars */
  const [forceRefresh, setForceRefresh] = useState({});
  const [file, setFile] = useState(null);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [pageLoading, setPageLoading] = useState(false);
  const [snackbarContent, setSnackbarContent] = useState();
  const [taskStatus, setTaskStatus] = useState();
  const { accessToken } = useContext(globalContext);
  /* eslint-enable */

  useEffect(() => {
    if (!createMode) {
      /** VIEW DETAIL MODE */
      setPageLoading(true);
      axios
          .get(`/v2/pttask/${correlationId}` /* options=*/, {
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
          })
          .then((resp) => {
            setTaskStatus(convertTaskStatus(taskStatus));
            populateDataToComponents(resp.data);
            setModel(model);
          })
          /* eslint-disable no-undef */
          .catch((error) =>
            console.log('Error Getting LoadTestingJob Detail', error),
          )
          .finally(() => setPageLoading(false));
      /* eslint-enable */
    }
  }, []);

  const handleCancelJob = () => {
    setPageLoading(true);
    setLoadingMessage('Cancelling Load Testing Job');
    axios
        .delete(`/v2/pttask/${correlationId}` /* options=*/, {
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        })
        /* eslint-disable no-undef */
        .then((resp) => console.log(resp))
        .catch((error) => console.log('ERROR Cancelling Job', error))
        .finally(() => {
          setPageLoading(false);
          setLoadingMessage('');
        });
    /* eslint-enable */
  };

  const handleResetClick = () => {
    model.nestedAttributes.forEach((attribute) => attribute.reset());
    selectedAttributeGroup.attributeData.value.repeatedValues.forEach(
        (attribute) => attribute.reset(),
    );

    setModel(model);
    setSelectedAttributeGroup(selectedAttributeGroup);
    setForceRefresh({});
  };

  const handleCreateTestClick = async () => {
    setPageLoading(true);
    setLoadingMessage('Creating Load Testing Job');

    const result = await uploadFile(file);

    if (result) {
      axios
          .post(
              `/v2/pttask`,
              /* requestBody=*/
              createRequestBody(
                  model,
                  selectedTaskType,
                  selectedAttributeGroup,
                  result.data.correlationId,
              ),
              /* options=*/
              {
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                },
              },
          )
          .then((response) => {
            /** Redirect Back To Listing Jobs Page upon successful creation */
            /* eslint-disable no-undef */
            setTimeout(() => {
              setPageLoading(false);
              setLoadingMessage('');
              window.location.href = '/webui';
            }, 5000);
            /* eslint-enable */
          })
          .catch((error) => {
            setSnackbarContent(
                `ERROR - Failed to Create Load Testing Job\n${error}`,
            );
            setPageLoading(false);
            setLoadingMessage('');
          });
    } else {
      setPageLoading(false);
      setSnackbarContent(`ERROR - Please Upload The Zip File`);
    }
  };

  const onSelectedComponentAlternativeChanged = (
      _selectedTaskType,
      incomingRepeatedValues = null,
  ) => {
    const _taskType = _selectedTaskType.toUpperCase();
    setSelectedTaskType(_taskType);
    const _selectedAttrGroup = attributeGroups.filter(
        (group) => group.id === _taskType,
    )[0];

    const _attributeData = new AttributeData(
        _selectedAttrGroup,
        new AttributeValue(
            null,
        incomingRepeatedValues ?
          incomingRepeatedValues :
          [new AttributeData(_selectedAttrGroup, new AttributeValue())],
        null,
        ),
    );

    setSelectedAttributeGroup({
      attribute: _selectedAttrGroup,
      attributeData: _attributeData,
    });
  };

  /**
   * UI helper function to bind Load Test job to its UI controls
   * @param {any} job
   */
  function populateDataToComponents(job) {
    /** first part of the model (non-dropdown subcomponents) */
    loadTestingJobAttributeData.nestedAttributes.forEach((attr) => {
      attr.value = new AttributeValue(
          getValueFromPtLaunchedTask(attr.attribute.id, job),
      );
    });

    const incomingRepeatedValues = populateRepeatedValues(
        convertTaskType(job.task.type),
        job,
    );

    /** set values for selected dropwon  */
    onSelectedComponentAlternativeChanged(
        convertTaskType(job.task.type),
        incomingRepeatedValues,
    );
  }

  /**
   * UI helper function to handle repeated values binding to its ui control.
   * @param {any} taskType
   * @param {any} job
   * @return {any}
   */
  function populateRepeatedValues(taskType, job) {
    const _selectedAttrGroup = attributeGroups.filter(
        (group) => group.id === taskType,
    )[0];

    return job.task.traffics?.map(
        (traffic) =>
          new AttributeData(
              _selectedAttrGroup,
              new AttributeValue(
                  null,
                  null,
                  convertArrayToMap(
                      _selectedAttrGroup.nestedAttributes,
                      (row) => row.id,
                      (row) =>
                        new AttributeData(
                            row,
                            new AttributeValue(
                                getValueFromPtLaunchedTask(row.id,
                                    job, traffic),
                            ),
                        ),
                  ),
              ),
          ),
    );
  }

  /**
   * Upload file to API backend from Form Data
   * @param {any} file
   * @return {any}
   */
  function uploadFile(file) {
    if (!file) return null;
    /* eslint-disable no-undef */
    const formData = new FormData();
    /* eslint-enable */
    formData.set('file', file);

    return axios.post(`/v2/pttask/scripts`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }

  return (
    <>
      {snackbarContent && <CustomSnackbar message={snackbarContent} />}

      <Backdrop
        sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
        open={pageLoading}>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
          }}>
          <CircularProgress color='inherit' />
          <span style={{ marginTop: 5 }}>{loadingMessage}...</span>
        </div>
      </Backdrop>
      {!pageLoading && (
        <Box sx={{ margin: '1rem', width: '500px' }}>
          <Typography
            variant='h6'
            component='h2'
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              marginBottom: '15px',
            }}>
            <span
              onClick={() => onClose()}
              style={{ cursor: 'pointer' }}
              className='google-symbols'>
              close
            </span>
          </Typography>
          {createMode && (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: '0.6rem',
              }}>
              <TextField
                disabled={true}
                value={file?.name ?? ''}
                sx={{ width: '100%', marginTop: '5px' }}
                size='small'
                required={true}
                label='File Name'
              />
              <Button
                variant='contained'
                sx={{ width: '200px', marginLeft: '0.5rem' }}
                component='label'>
                Upload Script
                <input
                  type='file'
                  hidden
                  onChange={(event) => {
                    const file = event.target.files[0];
                    setFile(file);
                  }}
                  accept='.tgz'></input>
              </Button>
            </span>
          )}

          {model.nestedAttributes.map((field) => {
            return (
              <AttributeField
                key={field.attribute.id}
                attribute={field.attribute}
                attributeData={field}
                parentValid={field.valid}
                readOnly={!createMode ? true : false}
              />
            );
          })}
          <Box sx={{ marginTop: '1rem' }}>
            <DropdownInput
              readOnly={!createMode ? true : false}
              attribute={{
                required: true,
                displayName: 'Task Type',
                id: 'taskType',
                options: ['LOCAL', 'LOAD DISTRIBUTION'],
                helpText: `Local/Distribution, Local - run the test on 
                  same GKE cluster, Distribution - run the test on 
                  different GKE cluster, which are in different region`,
                defaultValue: selectedTaskType,
              }}
              onValueChange={onSelectedComponentAlternativeChanged}
              attributeData={
                new AttributeData(
                    {
                      required: true,
                      displayName: 'Task Type',
                      id: 'taskType',
                    },
                    new AttributeValue(selectedTaskType),
                )
              }
            />
            {
              /** render content of selected Task Type option */
              selectedTaskType === 'LOAD DISTRIBUTION' && (
                <RepeatedField
                  attribute={selectedAttributeGroup.attribute}
                  attributeData={selectedAttributeGroup.attributeData}
                  hideTitle={true}
                  readOnly={!createMode ? true : false}
                />
              )
            }
            {createMode && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-start',
                  columnGap: '10px',
                }}>
                <Button
                  variant='contained'
                  sx={{ marginTop: '20px' }}
                  onClick={handleResetClick}>
                  <span>Reset</span>
                </Button>
                <Button
                  variant='contained'
                  sx={{ marginTop: '20px' }}
                  onClick={handleCreateTestClick}>
                  <span>Create Test</span>
                </Button>
              </div>
            )}
            {!createMode && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-start',
                  columnGap: '10px',
                }}>
                <Button
                  variant='contained'
                  disabled={taskStatus != 'Running'}
                  sx={{ marginTop: '20px' }}
                  onClick={handleCancelJob}>
                  <span>Cancel Job</span>
                </Button>
              </div>
            )}
          </Box>
        </Box>
      )}
    </>
  );
}

/**
 * Map between Task's properties to actual value from PT's Job object
 * @param {any} id
 * @param {any} job
 * @param {any} traffic
 * @return {any}
 */
function getValueFromPtLaunchedTask(id, job, traffic) {
  switch (id) {
    case 'targetUrl':
      return job.task.target_url;
    case 'totalUsers':
      return job.task.total_users;
    case 'duration':
      return job.task.duration;
    case 'rampUp':
      return job.task.ramp_up;
    case 'region':
      return traffic.region;
    case 'percent':
      return traffic.percent;
    case 'workers':
      return job.task.worker_number;
    default:
      return null;
  }
}

export { CreateOrViewLoadTestingJob };
