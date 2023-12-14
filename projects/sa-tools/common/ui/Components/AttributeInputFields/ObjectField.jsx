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

import { AttributeData, initValueInMap } from '../../CommonFunctions';
import { Box, Typography } from '@mui/material';
import { AttributeField } from './AttributeField';
import { HelpTooltip } from '../HelpTooltip';
import { useState, useEffect } from 'react';
import { Accordion, AccordionDetails, AccordionSummary } from '@mui/material';
import '../../css/satools.scss';

/**
 * Component to render Object input form fields
 * @param {!Object} objAttribute
 * @param {!AttributeData} attributeData
 * @param {boolean} [hideTitle=false] hide the title element when hideTitle = true
 * @return {JSX.Element}
 * @constructor
 */
function ObjectField({
  objAttribute,
  attributeData,
  hideTitle = false,
  parentValid = true,
  readOnly = false,
}) {
  const [forceRefresh, setForceRefresh] = useState();

  initValueInMap({
    dataMap: attributeData.value,
    key: 'nestedValues',
    defaultValue: {},
  });

  const nestedAttributes = objAttribute.nestedAttributes.map(
    (nestedAttribute, idx) => {
      const nestedAttributeData = initValueInMap({
        dataMap: attributeData.value.nestedValues,
        key: nestedAttribute.id,
        defaultValue: new AttributeData(nestedAttribute),
      });
      return (
        <AttributeField
          key={`${objAttribute.id}-${nestedAttribute.id}-${idx}`}
          style={{ marginTop: 15 }}
          attribute={nestedAttribute}
          attributeData={nestedAttributeData}
          parentValid={attributeData.valid}
          readOnly={readOnly}
        />
      );
    }
  );

  return (
    <Accordion
      sx={{
        marginBottom: '1rem',
        width: '93.8%',
        border: `${attributeData.valid ? '' : '1px solid red'}`,
      }}
      onBlur={(event) => {
        if (event.target.value === '') {
          /** Change Optional Section becomes .required = true
           *  When any of the children's value is ''
           */
          attributeData.attribute.required = true;
        } else {
          attributeData.validate();
          setTimeout(() => {
            setForceRefresh({});
          }, 1000);
        }
      }}>
      <AccordionSummary
        sx={{ marginBottom: 0 }}
        expandIcon={
          <span className='material-symbols-outlined'>expand_more</span>
        }
        aria-controls='panel1a-content'
        id='panel1a-header'>
        <Typography>
          {
            <span style={{ display: 'flex', alignItems: 'center' }}>
              {objAttribute.displayName ?? objAttribute.id}
              {!hideTitle && <HelpTooltip attribute={objAttribute} />}
            </span>
          }
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ paddingTop: '-10px!important' }}>
        <Box className='repeated-input-group'>{nestedAttributes}</Box>
      </AccordionDetails>
    </Accordion>
  );
}

export { ObjectField };
