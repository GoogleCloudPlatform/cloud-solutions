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
import {CommonModule, JsonPipe} from '@angular/common';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import {MatTabsModule} from '@angular/material/tabs';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {SqlStatementComponent} from '../../common/sql-statement/sql-statement.component';
import {
  CymbalShopsServiceClient,
  ExplainQueryResponse,
  ExplainPlanRow,
} from '../../services/cymbalshops-api'; // Adjust path as needed
import {SnackBarErrorComponent} from '../../common/SnackBarErrorComponent'; // Adjust path
import {Observable, of} from 'rxjs';
import {catchError, finalize, tap} from 'rxjs/operators';

// Interface for the data passed to the dialog
export interface SqlDialogData {
  productQuery: string | undefined;
  facetQuery: string | undefined;
}

@Component({
  selector: 'app-sql-viewer-dialog',
  standalone: true,
  imports: [
    CommonModule,
    JsonPipe, // Add JsonPipe for displaying results
    MatDialogModule,
    MatTabsModule,
    MatButtonModule,
    SqlStatementComponent,
    MatIconModule,
    MatProgressSpinnerModule, // Add for loading indicators
  ],
  templateUrl: './sql-viewer-dialog.component.html',
  styleUrls: ['./sql-viewer-dialog.component.scss'],
})
export class SqlViewerDialogComponent {
  // Observables to hold explain plan results
  productExplainResult$: Observable<ExplainQueryResponse<ExplainPlanRow> | null> =
    of(null);
  facetExplainResult$: Observable<ExplainQueryResponse<ExplainPlanRow> | null> =
    of(null);

  // Loading states
  productExplainLoading = false;
  facetExplainLoading = false;

  constructor(
    public dialogRef: MatDialogRef<SqlViewerDialogComponent>, // Keep MatDialogRef if you need to close programmatically
    @Inject(MAT_DIALOG_DATA) public data: SqlDialogData,
    private cymbalShopsClient: CymbalShopsServiceClient, // Inject the service
    private errorSnackbar: SnackBarErrorComponent // Inject error handler
  ) {}

  explainProductQuery() {
    if (!this.data.productQuery) {
      this.errorSnackbar.showError(
        'No product query available to explain.',
        ''
      );
      return;
    }
    this.productExplainLoading = true;
    this.productExplainResult$ = this.cymbalShopsClient
      .explainQuery(this.data.productQuery)
      .pipe(
        tap(response => console.log('Product Explain Plan:', response)),
        catchError(err => {
          this.errorSnackbar.showError(
            'Failed to fetch explain plan for product query.',
            err
          );
          return of(null); // Return null or an error object if you want to display specific error info
        }),
        finalize(() => {
          this.productExplainLoading = false;
        })
      );
  }

  explainFacetQuery() {
    if (!this.data.facetQuery) {
      this.errorSnackbar.showError('No facet query available to explain.', '');
      return;
    }
    this.facetExplainLoading = true;
    this.facetExplainResult$ = this.cymbalShopsClient
      .explainQuery(this.data.facetQuery)
      .pipe(
        tap(response => console.log('Facet Explain Plan:', response)),
        catchError(err => {
          this.errorSnackbar.showError(
            'Failed to fetch explain plan for facet query.',
            err
          );
          return of(null);
        }),
        finalize(() => {
          this.facetExplainLoading = false;
        })
      );
  }

  // Optional: Method to clear explain results if user switches tabs or re-explains
  clearProductExplain() {
    this.productExplainResult$ = of(null);
  }

  clearFacetExplain() {
    this.facetExplainResult$ = of(null);
  }
}
