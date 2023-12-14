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

import { AttributeData } from '../../CommonFunctions';
import Box from '@mui/material/Box';
import FormGroup from '@mui/material/FormGroup';
import FormLabel from '@mui/material/FormLabel';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import { HelpTooltip } from '../HelpTooltip';

/**
 * Checkbox functional Component that renders options of a multi-select String/Number field
 * @param attribute
 * @param {!AttributeData} attributeData
 * @return {JSX.Element}
 * @constructor
 */
function CheckboxField({ attribute, attributeData, parentValid }) {
  const checkOptions = attribute.options.map((field, idx) => {
    const defaultChecked =
      attribute.defaultValue?.simpleValue == field ?? 'defaultChecked';
    return (
      <FormControlLabel
        key={`${attribute.id}-opt-${idx}`}
        control={<Checkbox defaultChecked />}
        label={field}
      />
    );
  });

  return (
    <FormGroup>
      <Box
        sx={{
          borderRadius: '5px',
          padding: '10px',
          margin: '5px',
          height: 150,
          overflowY: 'scroll',
        }}>
        <FormGroup>
          <FormLabel component='legend'>
            <b style={{ color: 'black' }}>
              {attribute.displayName ? attribute.displayName : attribute.id}
            </b>
            <HelpTooltip attribute={attribute} />
          </FormLabel>
          {checkOptions}
        </FormGroup>
      </Box>
    </FormGroup>
  );
}

export { CheckboxField };
