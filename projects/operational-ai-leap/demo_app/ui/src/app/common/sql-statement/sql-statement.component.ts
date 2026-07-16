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

import {CommonModule} from '@angular/common';
import {
  Component,
  Input,
  OnChanges,
  SimpleChanges,
  AfterViewInit,
} from '@angular/core';
import {MatExpansionModule} from '@angular/material/expansion';

import {format} from 'sql-formatter';
import * as Prism from 'prismjs';

import 'prismjs/components/prism-sql.min.js';

@Component({
  selector: 'app-sql-statement',
  standalone: true,
  imports: [CommonModule, MatExpansionModule],
  templateUrl: './sql-statement.component.html',
  styleUrl: './sql-statement.component.scss',
})
export class SqlStatementComponent implements OnChanges, AfterViewInit {
  // Implement OnChanges

  @Input() query?: string | undefined;
  formattedQuery?: string;

  ngOnChanges(changes: SimpleChanges): void {
    // Use ngOnChanges
    if (changes['query']) {
      const newQuery = changes['query'].currentValue;
      if (newQuery) {
        this.query = format(newQuery, {language: 'postgresql'});
        Prism.highlightAll();
      } else {
        this.query = undefined;
      }
    }
  }

  ngAfterViewInit() {
    // Add ngAfterViewInit()
    Prism.highlightAll();
  }
}
