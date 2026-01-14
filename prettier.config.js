//
// Copyright 2026 Google LLC
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//

// The values of these options match Prettier v3.x defaults.
// We repeat them here for clarity, and in case they change in the future.
const prettierDefaults = {
  arrowParens: 'always',
  jsxSingleQuote: false,
  printWidth: 80,
  semi: true,
  singleAttributePerLine: false,
  tabWidth: 2,
  trailingComma: 'all',
  useTabs: false,
};

module.exports = {
  ...prettierDefaults,

  // Overrides for specific file types
  overrides: [
    {
      files: ['**/*.cts', '**/*.mts', '**/*.ts', '**/*.tsx'],
      options: {
        arrowParens: 'avoid',
        bracketSpacing: false,
        singleQuote: true,
        trailingComma: 'es5',
      },
    },
    // We can't enable Prettier to format JavaScript because there are certain
    // ESLint rules that conflict with the Google JavaScript style guide.
    // Keeping the following configuration here as a
    // reference.
    // {
    //   files: ['**/*.cjs', '**/*.js', '**/*.mjs', '**/*.jsx'],
    //   options: {
    //     bracketSameLine: true,
    //     bracketSpacing: false,
    //     embeddedLanguageFormatting: 'off',
    //     htmlWhitespaceSensitivity: 'strict',
    //     quoteProps: 'preserve',
    //     singleQuote: true,
    //   },
    // },
    {
      files: ['**/*.css', '**/*.sass', '**/*.scss'],
      options: {
        singleQuote: true,
      },
    },
    {
      files: '*.html',
      options: {
        printWidth: 100,
      },
    },
    {
      files: '*.acx.html',
      options: {
        parser: 'angular',
        singleQuote: true,
      },
    },
    {
      files: '*.ng.html',
      options: {
        parser: 'angular',
        singleQuote: true,
        printWidth: 100,
      },
    },
    {
      files: ['**/*.md'],
      options: {
        embeddedLanguageFormatting: 'off',
        proseWrap: 'always',
        // As recommended by the Google Markdown Style Guide
        // https://google.github.io/styleguide/docguide/style.html
        tabWidth: 4,
      },
    },
  ],
};
