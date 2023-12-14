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
import { Autocomplete, TextField } from '@mui/material';
import { HelpTooltip } from '../HelpTooltip';
import {
  AttributeData,
  checkAndExecuteFn,
  initValueInMap,
} from '../../CommonFunctions';

/**
 * Dropdown Menu functional Component that renders a single selection from list of options
 *
 * @param attribute
 * @param {!AttributeData} attributeData
 * @param {Function} onValueChange
 * @param {boolean} [hideTitle=false] hide the title element when hideTitle = true
 * @return {JSX.Element}
 * @constructor
 */
function DropdownInput({
  attribute,
  attributeData,
  onValueChange,
  hideTitle = false,
  parentValid = true,
  readOnly = false,
}) {
  const [valid, setValid] = useState(attributeData.valid);
  initValueInMap({
    dataMap: attributeData.value,
    key: 'simpleValue',
    defaultValue: null,
  });

  const [selectedItem, setSelectedItem] = useState(
    /* Priority given to attributeData.value (whether it has value populated already)
     Then if not check whether defaultValue exist for the attribute and use it
  */
    attributeData?.value?.simpleValue ??
      attribute.defaultValue?.simpleValue ??
      ''
  );

  useEffect(() => {
    /** we need true or false value but not undefined or null */
    setValid(parentValid);
  }, [parentValid]);

  return (
    <div
      style={{ display: 'flex', flexDirection: 'row', alignItems: 'center' }}>
      <Autocomplete
        disabled={readOnly}
        disablePortal
        value={selectedItem}
        options={attribute.options}
        sx={{ width: '100%' }}
        onChange={(event, newValue) => {
          attributeData.value.simpleValue = newValue;
          setSelectedItem(newValue);
          attributeData.validate();
          setValid(attributeData.valid);
          checkAndExecuteFn(onValueChange, newValue);
        }}
        renderInput={(params) => (
          //TODO (anantd): replace with TextInput
          <TextField
            {...params}
            label={attribute.displayName ?? attribute.id}
            required={attribute.required}
            error={!valid}
            disabled={readOnly}
          />
        )}
      />
      <HelpTooltip attribute={attribute} />
    </div>
  );
}

export { DropdownInput };
