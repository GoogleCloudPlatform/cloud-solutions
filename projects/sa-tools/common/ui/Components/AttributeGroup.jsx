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

import { AttributeField } from './AttributeInputFields/AttributeField';
import { AttributeData, initValueInMap } from '../CommonFunctions';

function AttributeGroup({ attributeGroup, attributeData, parentValid = true }) {
  return (
    <>
      {attributeGroup.attributes.map((attribute) => (
        <div
          style={{ marginTop: 15 }}
          key={`${Math.random().toString(32).substring(5)}-${attribute.id}`}>
          <AttributeField
            attribute={attribute}
            attributeData={initValueInMap({
              dataMap: attributeData,
              key: attribute.id,
              defaultValue: new AttributeData(attribute),
            })}
            parentValid={parentValid}
          />
        </div>
      ))}
    </>
  );
}

export { AttributeGroup };
