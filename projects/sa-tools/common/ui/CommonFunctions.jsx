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
 * Initializes a key in a map with provided defaultValue if it doesn't exist
 *
 * @param {!Object<!string, !any>} dataMap the parent map to update value
 * @param {!string} key the key to check in the map
 * @param {!any} defaultValue the default value to set
 * @return {!any} the value set for the key inside the parent map
 */
function initValueInMap({ dataMap, key, defaultValue }) {
  dataMap[key] = dataMap[key] ?? defaultValue;
  return dataMap[key];
}

class AttributeData {
  /**
   * @param {!Object} attribute
   * @param {AttributeValue} [value={}] the attribute's value
   * @param {boolean} [valid=true] the validity check result.
   */
  constructor(attribute, value = new AttributeValue(), valid = true) {
    this.attribute = attribute;
    this.value = value;
    this.valid = valid;
  }

  /**
   * Checks if the attribute is valid
   *
   * The function will check if the attribute is valid
   * by recursively drilling down the attribute tree.
   * It will also change the state of `valid` flag based on the result.
   *
   * @return {boolean} the attribute's validity
   */
  validate() {
    this.valid = (() => {
      if (this.attribute.repeated) {
        return !this.value.repeatedValues.some(
          (repeatedAttributeData) => !repeatedAttributeData.validate()
        );
      }

      switch (this.attribute.type) {
        case 'STRING':
        case 'NUMBER':
          this.valid =
            !this.attribute.required ||
            (this.value &&
              this.value.simpleValue != null &&
              this.value.simpleValue !== '');
          return this.valid;

        case 'OBJECT':
          /** The only way to change .required is within .value sub fields
           *  Hence, we need to skip validation when it is still optional
           *  .required could change if any of required child fields is entered.
           */
          if (!this.attribute.required) {
            return true;
          }
          return Object.values(this.value.nestedValues).every(
            (nestedAttributeData) => nestedAttributeData.validate()
          );
      }

      return true;
    })();

    return this.valid;
  }

  reset() {
    switch (this.attribute.type) {
      // TODO: Yudy to also handle repeated field and create unit test for it
      case 'STRING':
      case 'NUMBER':
        this.value.simpleValue = '';
        break;

      case 'OBJECT':
        return !Object.values(this.value.nestedValues).forEach(
          (nestedAttributeData) => nestedAttributeData.reset()
        );
    }
  }
}

class AttributeValue {
  /**
   *
   * @param {?string} simpleValue
   * @param {?Array<AttributeValue>} repeatedValues
   * @param {?Object<string, AttributeData>} nestedValues
   */
  constructor(simpleValue, repeatedValues, nestedValues) {
    this.simpleValue = simpleValue;
    this.repeatedValues = repeatedValues;
    this.nestedValues = nestedValues;
  }
}

class ComponentValidation {
  /**
   *
   * @param {!ComponentData} componentData
   */
  constructor(componentData) {
    this.componentData = componentData;
  }
}

/**
 * Performs a recursive validation of component attributes and sets the component's valid bit.
 *
 * @param {!ComponentData} componentData
 * @returns {boolean} true when the component is valid.
 */
function validateComponent(componentData) {
  return !Object.values(componentData.attributeData)
    .map((attribute) => attribute.validate())
    .some((valid) => !valid);
}

class ComponentData {
  /**
   *
   * @param {!Object} component
   * @param {Object<string,AttributeData>} attributeData
   * @param {Object} selectedAlternative
   * @param {boolean} [skipped=false]
   * @param {boolean} [valid
   */
  constructor(
    component,
    attributeData = {},
    selectedAlternative,
    skipped = false,
    valid = false
  ) {
    this.component = component;
    this.attributeData = attributeData;
    // this.selectedAlternative = selectedAlternative??;
    this.skipped = skipped;
    this.valid = valid;
  }
}

function convertMapTypeToRepeatedObjectType(mapAttribute) {
  const valueType = mapAttribute.mapValueType ??
    mapAttribute.nestedAttributes?.[0] ?? {
      id: `${mapAttribute.id}-value`,
      displayName: 'Value',
      type: 'STRING',
    };

  return {
    ...mapAttribute,
    type: 'OBJECT',
    repeated: true,
    nestedAttributes: [
      {
        id: `${mapAttribute.id}-key`,
        displayName: 'Key',
        type: 'STRING',
        defaultVisible: true,
      },
      {
        ...valueType,
        defaultVisible: true,
      },
    ],
  };
}

/**
 * Convert Array to HashMap
 *
 * Utility function to convert an Array to Hashmap
 * using the keyFn that computes the key from an
 * element or index of array
 *
 * Example: The following way will create a map
 * with id attribute as the key of the map
 * ```
 *   const arr = ...;
 *   arr.map(toHashMap((element)=> element.id));
 * ```
 *
 * @param {[]} arr
 * @param keyFn
 * @param valueFn
 * @returns {Map}
 */
function convertArrayToMap(arr, keyFn, valueFn = (x) => x) {
  if (typeof keyFn !== 'function') {
    throw 'KeyFn is undefined or not a function';
  }

  if (typeof valueFn !== 'function') {
    throw 'valueFn is undefined or not a function';
  }

  if (!arr || !Array.isArray(arr) || arr.length === 0) {
    return new Map();
  }

  return arr.reduce((map, element) => {
    map[keyFn(element)] = valueFn(element);
    return map;
  }, new Map());
}

/**
 * Executes the provided function {fn} if its a type of function and passes it all the arguments
 * @param {?function} fn
 * @param {*} args
 * @return {*} the return type of function or `undefined`
 */
function checkAndExecuteFn(fn, ...args) {
  if (fn && typeof fn === 'function') {
    return fn(...args);
  }
}

export {
  initValueInMap,
  AttributeData,
  AttributeValue,
  ComponentData,
  ComponentValidation,
  convertArrayToMap,
  convertMapTypeToRepeatedObjectType,
  validateComponent,
  checkAndExecuteFn,
};
