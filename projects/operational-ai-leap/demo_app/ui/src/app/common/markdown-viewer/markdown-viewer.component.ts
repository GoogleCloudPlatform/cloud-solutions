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

import {Component, Inject} from '@angular/core';
import {CommonModule} from '@angular/common';
import {MAT_DIALOG_DATA} from '@angular/material/dialog';
import * as marked from 'marked';

@Component({
  selector: 'app-markdown-viewer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './markdown-viewer.component.html',
  styleUrl: './markdown-viewer.component.scss',
})
export class MarkdownViewerComponent {
  parsedHtml: string | Promise<string> = '';

  constructor(
    @Inject(MAT_DIALOG_DATA)
    public data: {markdownSource: string | Promise<string>}
  ) {
    // eslint-disable-next-line n/no-unsupported-features/node-builtins
    fetch('assets/architecture.md')
      .then(response => response.text())
      .then(markdown => {
        console.log(JSON.stringify(markdown, null, 2));

        // Parse the markdown string into HTML
        this.parsedHtml = marked.parse(markdown);
      })
      .catch(error => {
        console.error('Error fetching or parsing Markdown:', error);
        // Handle the error appropriately (e.g., display an error message)
      });
  }
}
