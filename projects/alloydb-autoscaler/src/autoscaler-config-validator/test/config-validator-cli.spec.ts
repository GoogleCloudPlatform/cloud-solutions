/**
 * Copyright 2024 Google LLC
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

/** Tests config-validator-cli. */

import * as fs from 'node:fs';
import * as path from 'node:path';
import {TEST_ONLY} from '../config-validator-cli';
import {ConfigValidator} from '../../autoscaler-core/poller/config-validator';

describe('config-validator-cli', () => {
  const configValidator = new ConfigValidator();

  beforeAll(() => {
    // Silence console to make tests more readable.
    spyOn(console, 'log');
    spyOn(console, 'error');
  });

  describe('main', () => {
    const dir = 'src/autoscaler-config-validator/test/resources';
    const files = fs.readdirSync(dir, {withFileTypes: true});

    describe('yaml files', () => {
      const yamlFiles = files.filter(f => {
        return f.name.endsWith('.yaml') || f.name.endsWith('.yaml.txt');
      });

      yamlFiles
        .filter(f => f.name.startsWith('good-'))
        .forEach(file => {
          it(`validates file ${file.name} successfully`, () => {
            expect(() => {
              TEST_ONLY.validateFile(
                configValidator,
                path.join(dir, file.name)
              );
            }).not.toThrow();
          });
        });

      yamlFiles
        .filter(f => f.name.startsWith('bad-'))
        .forEach(file => {
          it(`invalid file ${file.name} correctly fails validation`, () => {
            expect(() => {
              TEST_ONLY.validateFile(
                configValidator,
                path.join(dir, file.name)
              );
            }).toThrow();
          });
        });
    });

    describe('json files', () => {
      const jsonFiles = files.filter(f => {
        return f.name.endsWith('.json') || f.name.endsWith('.json.txt');
      });

      jsonFiles
        .filter(f => f.name.startsWith('good-'))
        .forEach(file => {
          it(`validates file ${file.name} successfully`, () => {
            expect(() => {
              TEST_ONLY.validateFile(
                configValidator,
                path.join(dir, file.name)
              );
            }).not.toThrow();
          });
        });

      jsonFiles
        .filter(f => f.name.startsWith('bad-'))
        .forEach(file => {
          it(`invalid file ${file.name} correctly fails validation`, () => {
            expect(() => {
              TEST_ONLY.validateFile(
                configValidator,
                path.join(dir, file.name)
              );
            }).toThrow();
          });
        });
    });
  });
});
