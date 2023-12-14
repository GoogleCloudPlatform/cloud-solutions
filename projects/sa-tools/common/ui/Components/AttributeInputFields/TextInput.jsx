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

import { useEffect, useState } from 'react';
import { AttributeData, initValueInMap } from '../../CommonFunctions';
import { TextField } from '@mui/material';
import { HelpTooltip } from '../HelpTooltip';
import { ExampleInput } from '../ExampleInput';

/**
 * TextInput functional Component that renders String/Number input form field
 *
 * @param attribute
 * @param {!AttributeData} attributeData
 * @param {boolean} [hideTitle=false] hide the title element when hideTitle = true
 * @param {boolean} parentValid mark the parent as invalid
 * @return {JSX.Element}
 * @constructor
 */
function TextInput({
  attribute,
  attributeData,
  hideTitle = false,
  parentValid,
  readOnly = false,
}) {
  const [inputValue, setInputValue] = useState(
    attributeData.attribute.defaultValue?.simpleValue ?? ''
  );
  const [forceRefresh, setForceRefresh] = useState();

  useEffect(() => {
    if (parentValid === false) {
      attributeData.validate();
      setForceRefresh({});
    }
  }, [parentValid]);

  useEffect(() => {
    if (attributeData.value.simpleValue != null) {
      setInputValue(attributeData.value.simpleValue);
    }
  }, [attributeData.value?.simpleValue ?? attributeData]);

  return (
    <span style={{ width: '100%' }}>
      <TextField
        disabled={readOnly}
        error={!attributeData.valid}
        required={attribute.required}
        label={attribute.displayName ?? attribute.id}
        value={inputValue}
        onChange={(event) => setInputValue(event.target.value)}
        onBlur={(event) => {
          attributeData.value['simpleValue'] = event.target.value;
          attributeData.validate();
          setForceRefresh({});
        }}
        sx={{ width: '100%', marginTop: '5px' }}
        size='small'
        InputProps={{
          endAdornment: <HelpTooltip attribute={attribute} />,
        }}
        variant='outlined'
      />
      <ExampleInput attribute={attribute}></ExampleInput>
    </span>
  );
}

export { TextInput };
