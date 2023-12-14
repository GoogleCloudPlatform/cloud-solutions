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

import { TextInput } from './TextInput';
import { ToggleSwitchInput } from './ToggleSwitchInput';
import { DropdownInput } from './DropdownInput';
import { ObjectField } from './ObjectField';
import { RepeatedField } from './RepeatedField';
import { CheckboxField } from './CheckboxField';
import { MapInput } from './MapInput';

/**
 * Input Field Component that renders Form input elements conditionally
 */
function AttributeField({
  attribute,
  attributeData,
  hideTitle = false,
  parentValid = true,
  readOnly = false,
}) {
  if (!attribute.defaultVisible) {
    return <></>;
  }

  if (attribute.repeated) {
    if (attribute.options && attribute.options.length > 0) {
      return (
        <CheckboxField
          attribute={attribute}
          attributeData={attributeData}
          parentValid={parentValid}
        />
      );
    }

    return (
      <RepeatedField
        attribute={attribute}
        attributeData={attributeData}
        parentValid={parentValid}
        readOnly={readOnly}
      />
    );
  }

  switch (attribute.type) {
    case 'BOOLEAN':
      return (
        <ToggleSwitchInput
          attribute={attribute}
          attributeData={attributeData}
          hideTitle={hideTitle}
          readOnly={readOnly}
        />
      );

    default:
    case 'STRING':
    case 'NUMBER':
      if (attribute.options) {
        return (
          <DropdownInput
            attribute={attribute}
            attributeData={attributeData}
            hideTitle={hideTitle}
            parentValid={parentValid}
            readOnly={readOnly}
          />
        );
      }

      return (
        <TextInput
          attribute={attribute}
          attributeData={attributeData}
          hideTitle={hideTitle}
          parentValid={parentValid}
          readOnly={readOnly}
        />
      );

    case 'OBJECT':
      return (
        <ObjectField
          objAttribute={attribute}
          attributeData={attributeData}
          hideTitle={hideTitle}
          parentValid={parentValid}
          readOnly={readOnly}
        />
      );

    case 'MAP':
      return (
        <MapInput
          mapAttribute={attribute}
          attributeData={attributeData}
          hideTitle={hideTitle}
          parentValid={parentValid}
          readOnly={readOnly}
        />
      );
  }
}

export { AttributeField };
