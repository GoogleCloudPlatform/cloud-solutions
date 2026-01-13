/*
* Copyright 2026 Google LLC
*
* Licensed to the Apache Software Foundation (ASF) under one
* or more contributor license agreements.  See the NOTICE file
* distributed with this work for additional information
* regarding copyright ownership.  The ASF licenses this file
* to you under the Apache License, Version 2.0 (the
* "License"); you may not use this file except in compliance
* with the License.  You may obtain a copy of the License at
*
*   http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing,
* software distributed under the License is distributed on an
* "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
* KIND, either express or implied.  See the License for the
* specific language governing permissions and limitations
* under the License.
*/

import { defineConfig, globalIgnores } from "eslint/config";
import n from "eslint-plugin-n";
import prettier from "eslint-plugin-prettier";
import globals from "globals";
import parser from "jsonc-eslint-parser";
import tsParser from "@typescript-eslint/parser";
import path from "node:path";
import { fileURLToPath } from "node:url";
import js from "@eslint/js";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
    baseDirectory: __dirname,
    recommendedConfig: js.configs.recommended,
    allConfig: js.configs.all
});

export default defineConfig([globalIgnores(["!**/.*", "**/node_modules/.*", "**/vite-env.d.ts"]), {
    extends: compat.extends("eslint:recommended"),

    plugins: {
        n,
        prettier,
    },

    languageOptions: {
        globals: {
            ...globals.browser,
            ...globals.node,
        },
    },

    rules: {},
}, {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs", "**/*.jsx"],
    extends: compat.extends("plugin:react/recommended"),

    languageOptions: {
        ecmaVersion: "latest",
        sourceType: "module",

        parserOptions: {
            ecmaFeatures: {
                jsx: true,
                modules: true,
                experimentalObjectRestSpread: true,
            },
        },
    },

    rules: {
        "array-bracket-newline": "off",
        "array-bracket-spacing": ["error", "never"],
        "array-element-newline": "off",
        "arrow-parens": ["error", "always"],
        "block-spacing": ["error", "never"],
        "brace-style": "error",

        camelcase: ["error", {
            properties: "never",
        }],

        "comma-dangle": ["error", "always-multiline"],
        "comma-spacing": "error",
        "comma-style": "error",
        "computed-property-spacing": "error",
        "constructor-super": "error",
        curly: ["error", "multi-line"],
        "eol-last": "error",
        "func-call-spacing": "error",
        "generator-star-spacing": ["error", "after"],
        "guard-for-in": "error",

        indent: ["error", 2, {
            CallExpression: {
                arguments: 2,
            },

            FunctionDeclaration: {
                body: 1,
                parameters: 2,
            },

            FunctionExpression: {
                body: 1,
                parameters: 2,
            },

            MemberExpression: 2,
            ObjectExpression: 1,
            SwitchCase: 1,
            ignoredNodes: ["ConditionalExpression"],
        }],

        "key-spacing": "error",
        "keyword-spacing": "error",
        "linebreak-style": "error",

        "max-len": ["error", {
            code: 80,
            tabWidth: 2,
            ignoreUrls: true,
        }],

        "new-cap": "error",
        "no-array-constructor": "error",
        "no-caller": "error",
        "no-cond-assign": "off",
        "no-extend-native": "error",
        "no-extra-bind": "error",
        "no-invalid-this": "error",
        "no-irregular-whitespace": "error",
        "no-mixed-spaces-and-tabs": "error",
        "no-multi-spaces": "error",
        "no-multi-str": "error",

        "no-multiple-empty-lines": ["error", {
            max: 2,
        }],

        "no-new-symbol": "error",
        "no-new-wrappers": "error",
        "no-throw-literal": "error",
        "no-this-before-super": "error",
        "no-unexpected-multiline": "error",

        "no-unused-vars": ["error", {
            args: "none",
        }],

        "no-var": "error",
        "no-with": "error",
        "prefer-promise-reject-errors": "error",
        "no-new-object": "error",
        "no-tabs": "error",
        "no-trailing-spaces": "error",
        "object-curly-spacing": ["error"],

        "one-var": ["error", {
            var: "never",
            let: "never",
            const: "never",
        }],

        "operator-linebreak": ["error", "after"],
        "padded-blocks": ["error", "never"],

        "prefer-const": ["error", {
            destructuring: "all",
        }],

        "prefer-rest-params": "error",
        "prefer-spread": "error",
        "rest-spread-spacing": "error",
        "quote-props": ["error", "consistent"],

        quotes: ["error", "single", {
            allowTemplateLiterals: true,
        }],

        semi: "error",
        "semi-spacing": "error",
        "space-before-blocks": "error",

        "space-before-function-paren": ["error", {
            asyncArrow: "always",
            anonymous: "never",
            named: "never",
        }],

        "spaced-comment": ["error", "always"],
        "switch-colon-spacing": "error",
        "yield-star-spacing": ["error", "after"],
    },
}, {
    files: ["**/*.json"],
    extends: compat.extends("plugin:jsonc/recommended-with-json"),

    languageOptions: {
        parser: parser,
        ecmaVersion: 5,
        sourceType: "script",

        parserOptions: {
            jsonSyntax: "JSON",
        },
    },

    rules: {
        "max-len": ["off"],
    },
}, {
    files: ["**/*.jsonc"],
    extends: compat.extends("plugin:jsonc/recommended-with-jsonc"),

    languageOptions: {
        parser: parser,
        ecmaVersion: 5,
        sourceType: "script",

        parserOptions: {
            jsonSyntax: "JSONC",
        },
    },

    rules: {
        "max-len": ["off"],
    },
}, {
    files: ["**/*.json5"],
    extends: compat.extends("plugin:jsonc/recommended-with-json5"),

    languageOptions: {
        parser: parser,
        ecmaVersion: 5,
        sourceType: "script",

        parserOptions: {
            jsonSyntax: "JSON5",
        },
    },

    rules: {
        "max-len": ["off"],
    },
}, {
    files: ["**/*.ts", "**/*.cts", "**/*.mts", "**/*.tsx"],

    extends: compat.extends(
        "plugin:@typescript-eslint/recommended",
        "plugin:n/recommended",
        "plugin:react/recommended",
        "prettier",
    ),

    languageOptions: {
        parser: tsParser,
        ecmaVersion: 2018,
        sourceType: "module",
    },

    rules: {
        "@typescript-eslint/ban-ts-comment": "warn",
        "@typescript-eslint/ban-types": "off",
        "@typescript-eslint/camelcase": "off",
        "@typescript-eslint/explicit-function-return-type": "off",
        "@typescript-eslint/explicit-module-boundary-types": "off",
        "@typescript-eslint/no-empty-function": "off",
        "@typescript-eslint/no-non-null-assertion": "off",
        "@typescript-eslint/no-use-before-define": "off",
        "@typescript-eslint/no-var-requires": "off",
        "@typescript-eslint/no-warning-comments": "off",
        "n/no-empty-function": "off",
        "n/no-missing-import": "off",
        "n/no-missing-require": "off",
        "n/no-unsupported-features/es-syntax": "off",
        "n/shebang": "off",
        "prettier/prettier": "error",
        "block-scoped-var": "error",
        "eol-last": "error",
        eqeqeq: "error",
        "no-dupe-class-members": "off",

        "no-restricted-properties": ["error", {
            object: "describe",
            property: "only",
        }, {
            object: "it",
            property: "only",
        }],

        "no-trailing-spaces": "error",
        "no-var": "error",
        "prefer-arrow-callback": "error",
        "prefer-const": "error",
        "require-atomic-updates": "off",

        quotes: ["warn", "single", {
            avoidEscape: true,
        }],
    },
}]);
