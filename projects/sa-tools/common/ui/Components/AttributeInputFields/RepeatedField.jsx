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
import { AttributeField } from './AttributeField';
import { HelpTooltip } from '../HelpTooltip';
import { WhiteButton } from '../WhiteButton';

/**
 * Renders repeated attribute
 *
 * @param attribute
 * @param {!AttributeData} attributeData
 * @constructor
 */
function RepeatedField({
  attribute,
  attributeData,
  hideTitle = false,
  parentValid = true,
  readOnly = false,
}) {
  const nonRepeatedAttribute = { ...attribute, repeated: false };

  const initValue = attribute.required
    ? [new AttributeData(nonRepeatedAttribute)]
    : [];

  initValueInMap({
    dataMap: attributeData.value,
    key: 'repeatedValues',
    defaultValue: initValue,
  });
  const [forceRefresh, setForceRefresh] = useState(null);
  const addElement = () => {
    attributeData.value.repeatedValues.push(
      new AttributeData(nonRepeatedAttribute)
    );
    setForceRefresh({});
  };

  const removeElement = (itemIndex) => {
    attributeData.value.repeatedValues.splice(itemIndex, 1);
    setForceRefresh({});
  };
  return (
    <div>
      <span
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          marginTop: '20px',
        }}>
        {!hideTitle && (
          <span>
            <b>
              {attribute.displayName ? attribute.displayName : attribute.id}
            </b>

            <HelpTooltip attribute={attribute} />
          </span>
        )}
      </span>
      {attributeData.value.repeatedValues.map((itemData, itemIndex) => (
        <div key={`${attribute.id + itemIndex}`}>
          <span
            style={{
              display: 'flex',
              flexDirection: 'row',
              marginTop: '0px',
              marginBottom: '0px',
            }}>
            <AttributeField
              attribute={nonRepeatedAttribute}
              attributeData={itemData}
              hideTitle={true}
              parentValid={parentValid}
              readOnly={readOnly}
            />
            <span
              onClick={() => removeElement(itemIndex)}
              style={{ cursor: 'pointer', marginLeft: 5, marginTop: '1rem' }}
              className='google-symbols'>
              delete
            </span>
          </span>
        </div>
      ))}
      {!readOnly && (
        <WhiteButton onClick={addElement}>
          <span
            style={{ cursor: 'pointer', marginRight: '5px' }}
            className='google-symbols'>
            add
          </span>
          Add
        </WhiteButton>
      )}
    </div>
  );
}

export { RepeatedField };
