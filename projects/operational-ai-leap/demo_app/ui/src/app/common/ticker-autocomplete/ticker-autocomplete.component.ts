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

import {Component, EventEmitter, Output} from '@angular/core';
import {FormControl, FormsModule, ReactiveFormsModule} from '@angular/forms';
import {Observable, catchError, map} from 'rxjs';
import {AsyncPipe} from '@angular/common';
import {MatSelectModule} from '@angular/material/select';
import {MatInputModule} from '@angular/material/input';
import {MatFormFieldModule} from '@angular/material/form-field';
import {CymbalShopsServiceClient} from '../../services/cymbalshops-api';
import {SnackBarErrorComponent} from '../SnackBarErrorComponent';

/**
 * @title Ticker symbol autocomplete
 */
@Component({
  selector: 'app-ticker-autocomplete',
  templateUrl: 'ticker-autocomplete.component.html',
  styleUrl: 'ticker-autocomplete.component.scss',
  standalone: true,
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    ReactiveFormsModule,
    SnackBarErrorComponent,
    AsyncPipe,
  ],
})
export class TickerAutocompleteComponent {
  tickerControl = new FormControl('');
  tickers?: Observable<string[]>;

  constructor(
    private CymbalShopsClient: CymbalShopsServiceClient,
    private error: SnackBarErrorComponent
  ) {
    this.tickers = this.CymbalShopsClient.getTickers().pipe(
      // sort tickers alphabetically
      map(tickers => tickers.sort()),
      catchError(err => {
        this.error.showError('Unable to load tickers', err);
        return [];
      })
    );
  }

  @Output()
  tickerSelected = new EventEmitter<string>();

  onTickerSelected(ticker: string) {
    this.tickerSelected.emit(ticker);
  }
}
