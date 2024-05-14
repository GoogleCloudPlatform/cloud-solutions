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

import { useState } from 'react';
import { Box, Button } from '@mui/material';
import Typography from '@mui/material/Typography';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';

import { AttributeGroup } from './AttributeGroup';
import { DropdownInput } from './AttributeInputFields/DropdownInput';
import {
  AttributeData,
  checkAndExecuteFn,
  initValueInMap,
  validateComponent,
} from '../CommonFunctions';
import '../css/satools.scss';

/** Basic Modal functional Component that renders */
function FormModal({
  component,
  componentData,
  handleClose,
  onSkip,
  onValidate,
}) {
  initValueInMap({
    dataMap: componentData,
    key: 'selectedAlternative',
    defaultValue: new AttributeData({
      id: `alternative-${component.componentId}`,
      displayName: 'Select Alternative',
      type: 'STRING',
      required: true /**  make selectedAlternative also mandatory */,
      helpText: `Select alternative for ${component.componentType}`,
      options: component.componentAlternatives?.alternatives.map(
        (component) => component.componentType
      ),
    }),
  });

  // We need to factor when componentAlternatives only have one item
  // Single item component also will be stored inside ComponentAlternatives
  const [attributeGroups, setAttributeGroups] = useState(
    componentData.selectedAlternative?.attributeGroups
  );

  const [selectedTab, setSelectedTab] = useState(0);
  const [selectedComponentAlternative, setSelectedComponentAlternative] =
    useState(componentData.selectedAlternative);
  const [formValid, setFormValid] = useState(true);

  const handleSkip = () => {
    checkAndExecuteFn(onSkip, component);
    handleClose();
  };

  /** If any of the children's componentData valid=false, then
  *  also trigger .validate() for all children
  */
  const handleValidate = () => {
    if (componentData.attributeData) {
      componentData.valid = validateComponent(componentData);

      setFormValid(componentData.valid);
      /** set also ComponentValidation state on parent by signalling it */
      checkAndExecuteFn(onValidate, componentData);

      if (componentData.valid) {
        handleClose();
      }
    }
  };

  const onSelectedComponentAlternativeChanged = (newValue) => {
    const selectedComponent =
      component.componentAlternatives.alternatives.filter(
        (comp) => comp.componentType === newValue
      )[0];

    const selectedAttributeGroups = selectedComponent.attributeGroups;

    /** clearing out fields */
    delete componentData['attributeData'];

    componentData['component'] = {
      ...selectedComponent,
      componentId: component.componentId,
    };

    componentData['selectedAlternative'] = {
      ...selectedComponentAlternative,
      value: {
        simpleValue: newValue,
      },
      valid: true,
      validate: () => true,
      attributeGroups: selectedAttributeGroups,
    };
    setSelectedComponentAlternative(componentData['selectedAlternative']);

    setAttributeGroups(selectedAttributeGroups);
  };

  return (
    <div>
      <Box
        style={{
          padding: '2rem',
          width: '520px',
          marginBottom: '4rem',
        }}
        id='component-form-modal-box'>
        <Typography
          id='modal-modal-title'
          variant='h6'
          component='h2'
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: '15px',
          }}>
          {`Details for ${component.componentType} ${
            component.displayName ? '(' + component.displayName + ')' : ''
          }`}
          <span
            onClick={handleClose}
            style={{ cursor: 'pointer' }}
            className='google-symbols'>
            close
          </span>
        </Typography>
        <DropdownInput
          attribute={selectedComponentAlternative.attribute}
          onValueChange={onSelectedComponentAlternativeChanged}
          attributeData={selectedComponentAlternative}
        />
        {attributeGroups && (
          <>
            {/* Start of rendering code for Grouped Attributes */}
            {
              <Tabs
                variant='scrollable'
                scrollButtons='auto'
                value={selectedTab}
                onChange={(event, newValue) => {
                  setSelectedTab(newValue);
                }}>
                {attributeGroups.groups.map((attributeGroup, groupIndex) => (
                  <Tab
                    key={`attribute-group-tab-${groupIndex}`}
                    label={attributeGroup.name}
                    value={groupIndex}
                    aria-controls={`tabpanel-${component.componentId}-${attributeGroup.id}`}
                    id={`attribute-group-tab-${groupIndex}`}
                  />
                ))}
              </Tabs>
            }
            {attributeGroups.groups.map((attributeGroup, groupIndex) => (
              <div
                key={`attribute-group-tabpanel-${groupIndex}`}
                role='tabpanel'
                onChange={(event) => event.stopPropagation()}
                id={`tabpanel-${component.componentId}-${attributeGroup.id}`}
                hidden={selectedTab !== groupIndex}
                aria-labelledby={`tab-${component.componentId}-${attributeGroup.id}`}>
                <AttributeGroup
                  attributeGroup={attributeGroup}
                  attributeData={initValueInMap({
                    dataMap: componentData,
                    key: 'attributeData',
                    defaultValue: {},
                  })}
                  parentValid={formValid}
                />
              </div>
            ))}
            {/* End of rendering code for Grouped Attributes */}
          </>
        )}
      </Box>
      <div
        style={{
          borderTop: '1px solid #c4c4c4',
          position: 'fixed',
          bottom: '0',
          width: '100%',
          backgroundColor: 'white',
          opacity: '1',
          zIndex: '10',
        }}>
        <Button
          variant='contained'
          style={{ marginLeft: '1rem' }}
          color='success'
          onClick={handleValidate}>
          VALIDATE
        </Button>
        <Button
          variant='outlined'
          onClick={handleSkip}
          style={{ margin: '1rem' }}
          color='warning'>
          SKIP COMPONENT
        </Button>
      </div>
    </div>
  );
}

export { FormModal };
