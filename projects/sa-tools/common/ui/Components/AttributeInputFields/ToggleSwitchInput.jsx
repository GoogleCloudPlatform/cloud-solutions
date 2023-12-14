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
import { AttributeData, initValueInMap } from '../../CommonFunctions';
import FormGroup from '@mui/material/FormGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import { HelpTooltip } from '../HelpTooltip';

/**
 * Toggle Switch functional Component that renders Boolean Value input form field
 *
 * @param attribute
 * @param {!AttributeData} attributeData
 * @param {boolean} [hideTitle=false] hide the title element when hideTitle = true
 */
function ToggleSwitchInput({
  attribute,
  attributeData,
  hideTitle = false,
  readOnly = false,
}) {
  initValueInMap({
    dataMap: attributeData.value,
    key: 'simpleValue',
    defaultValue:
      attributeData.attribute.defaultValue?.simpleValue === 'true'
        ? true
        : false,
  });

  const [toggleState, setToggleState] = useState(
    attributeData.value.simpleValue
  );

  return (
    <>
      <FormGroup>
        <FormControlLabel
          control={
            <Switch
              disabled={readOnly}
              checked={toggleState}
              onChange={(event) => {
                attributeData.value.simpleValue = event.target.checked;
                setToggleState(event.target.checked);
                attributeData.validate();
              }}
              inputProps={{ 'aria-label': 'controlled' }}
            />
          }
          label={
            <span style={{ display: 'flex', alignItems: 'center' }}>
              {!hideTitle && (attribute.displayName ?? attribute.id)}
              <HelpTooltip attribute={attribute} />
            </span>
          }
        />
      </FormGroup>
    </>
  );
}

export { ToggleSwitchInput };
