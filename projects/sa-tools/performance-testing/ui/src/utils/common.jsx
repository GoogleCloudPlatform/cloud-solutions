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

/**
 * Helper function to generate Performance Testing's Job request body
 * @param {any} model
 * @param {any} selectedTaskType
 * @param {any} selectedAttributeGroup
 * @param {any} correlationId
 * @return {any}
 */
function createRequestBody(
    model,
    selectedTaskType,
    selectedAttributeGroup,
    correlationId,
) {
  const requestBody = {
    correlation_id: correlationId,
    total_users: parseInt(
        findAttributeValue(
            model.nestedAttributes,
            'totalUsers',
        ),
    ),
    duration: parseInt(findAttributeValue(model.nestedAttributes, 'duration')),
    ramp_up: parseInt(findAttributeValue(model.nestedAttributes, 'rampUp')),
    type: invertTaskType(selectedTaskType),
    target_url: findAttributeValue(model.nestedAttributes, 'targetUrl'),
    worker_number: parseInt(
        findAttributeValue(model.nestedAttributes, 'workers'),
    ),
  };
  if (selectedTaskType !== 'LOCAL') {
    requestBody['traffics'] = findAttributeValue(
        selectedAttributeGroup.attributeData.value.repeatedValues,
        '', /* when fieldName empty we'll assume LOAD DISTRIBUTION */
    );
  }
  return requestBody;
}

/**
 * Helper function to extract dynamic form's attribute's value entered.
 * @param {any} nestedAttributes
 * @param {any} fieldName
 * @return {any}
 */
function findAttributeValue(nestedAttributes, fieldName) {
  const objectValues = [];
  /** meaning LOAD DISTRIBUTION option */
  if (!fieldName) {
    nestedAttributes.forEach((attributeData) => {
      objectValues.push({
        region: attributeData.value.nestedValues['region'].value.simpleValue,
        percent: parseInt(
            attributeData.value.nestedValues['percent'].value.simpleValue,
        ),
      });
    });
    return objectValues;
  } else {
    /** simpleValue type */
    return (
      nestedAttributes.find(
          (attributeData) => attributeData.attribute.id === fieldName,
      )?.value.simpleValue ?? ''
    );
  }
}

/**
 * Helper function to convert given dropdown of Performance Testing's Task Type
 * @param {any} type
 * @return {any}
 */
function convertTaskType(type) {
  switch (type) {
    case 1:
      return 'LOCAL';
    case 2:
      return 'LOAD DISTRIBUTION';
    default:
      return 'UNKNOWN Task Type';
  }
}

/**
 * Helper function to convert given Performance Testing's Task Type
 * to number key
 * @param {any} type
 * @return {any}
 */
function invertTaskType(type) {
  switch (type) {
    case 'LOCAL':
      return 1;
    case 'LOAD DISTRIBUTION':
      return 2;
    default:
      return 0;
  }
}

/**
 * Helper function to convert given enum to provision status string
 * @param {any} provisionStatus
 * @return {any}
 */
function convertProvisionStatus(provisionStatus) {
  switch (provisionStatus) {
    case 1:
      return 'Provisioning';
    case 2:
      return 'Provisioning Finished';
    case 3:
      return 'Provisioning Failed';
    default:
      return 'Unknown Status';
  }
}

/**
 * Helper function to convert given enum key to Task Status string
 * @param {any} status
 * @return {any}
 */
function convertTaskStatus(status) {
  switch (status) {
    case 1:
      return 'Pending';
    case 2:
      return 'Running';
    case 3:
      return 'Finished';
    case 4:
      return 'Failed';
    case 5:
      return 'Cancelling';
    case 6:
      return 'Cancelled';
    default:
      return 'Unknown Status';
  }
}

export {
  findAttributeValue,
  createRequestBody,
  convertTaskType,
  convertProvisionStatus,
  convertTaskStatus,
};
