/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'background': '#0b1326',
        'surface': {
          'DEFAULT': '#0b1326',
          'dim': '#0b1326',
          'bright': '#31394d',
          'container-lowest': '#060e20',
          'container-low': '#131b2e',
          'container': '#171f33',
          'container-high': '#222a3d',
          'container-highest': '#2d3449',
          'tint': '#adc7ff',
          'variant': '#2d3449',
        },
        'on-surface': {
          DEFAULT: '#dae2fd',
          variant: '#c1c6d6',
        },
        'border-high-fidelity': '#334155',
        'outline': {
          DEFAULT: '#8b909f',
          variant: '#414754',
        },
        'primary': {
          'DEFAULT': '#adc7ff',
          'container': '#1a73e8',
          'on-container': '#ffffff',
          'fixed': '#d8e2ff',
          'fixed-dim': '#adc7ff',
        },
        'secondary': {
          'DEFAULT': '#6ddd81',
          'container': '#30a550',
          'on-container': '#003210',
        },
        'status': {
          critical: '#D93025',
          warning: '#FBBC04',
        },
        'cyber': {
          blue: '#00f0ff',
          green: '#00ff66',
          red: '#ff0055',
          amber: '#ffaa00',
          purple: '#a855f7',
        },
      },
      fontFamily: {
        headline: ['var(--font-hanken)', 'sans-serif'],
        sans: ['var(--font-inter)', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'monospace'],
      },
      borderRadius: {
        sm: '0.125rem',
        DEFAULT: '0.25rem',
        md: '0.375rem',
        lg: '0.5rem',
        xl: '0.75rem',
      },
      spacing: {
        'grid-margin': '2rem',
        'grid-gutter': '1.5rem',
        'section-gap': '4rem',
        'component-padding': '1rem',
        'data-density-sm': '0.5rem',
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink-red': 'blinkRed 1.2s infinite alternate',
        'anomaly-glow': 'anomalyGlow 1.5s infinite alternate',
      },
      keyframes: {
        blinkRed: {
          '0%': {
            backgroundColor: 'rgba(217, 48, 37, 0.15)',
            borderColor: '#D93025',
          },
          '100%': {
            backgroundColor: 'rgba(217, 48, 37, 0.35)',
            borderColor: '#ff6b60',
            boxShadow: '0 0 25px rgba(217, 48, 37, 0.6)',
          },
        },
        anomalyGlow: {
          '0%': {
            borderColor: '#D93025',
            boxShadow:
              '0 0 10px rgba(217, 48, 37, 0.3), ' +
              'inset 0 0 8px rgba(217, 48, 37, 0.2)',
          },
          '100%': {
            borderColor: '#ff6b60',
            boxShadow:
              '0 0 25px rgba(217, 48, 37, 0.7), ' +
              'inset 0 0 15px rgba(217, 48, 37, 0.5)',
          },
        },
      },
    },
  },
  plugins: [],
};
