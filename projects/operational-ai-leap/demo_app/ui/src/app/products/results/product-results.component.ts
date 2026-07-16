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

import {
  Component,
  Input,
  Output,
  EventEmitter,
  ChangeDetectorRef,
  OnInit,
  OnDestroy,
} from '@angular/core';
import {CommonModule} from '@angular/common';
import {
  QueryResponse,
  Product,
  FacetResponse,
  RawFacet,
  FacetGroup,
  Facet,
} from '../../services/cymbalshops-api';
import {Observable, Subscription, map} from 'rxjs';
import {MatCardModule} from '@angular/material/card';
import {MatExpansionModule} from '@angular/material/expansion';
import {MatTableModule} from '@angular/material/table';
import {MatTabsModule} from '@angular/material/tabs';
import {MatDividerModule} from '@angular/material/divider';
import {MatListModule} from '@angular/material/list';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatIconModule} from '@angular/material/icon';
import {MatGridListModule} from '@angular/material/grid-list';
import {MatButtonModule} from '@angular/material/button';
import {MatDialog, MatDialogModule} from '@angular/material/dialog';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {TextToHtmlPipe} from '../../common/text-to-html.pipe';
import {SqlStatementComponent} from '../../common/sql-statement/sql-statement.component';
import {SqlViewerDialogComponent} from '../sql-viewer-dialog/sql-viewer-dialog.component';
import {RoleService} from '../../services/cymbalshops-api';

@Component({
  selector: 'app-product-results',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatExpansionModule,
    SqlStatementComponent,
    TextToHtmlPipe,
    MatTableModule,
    MatDividerModule,
    MatListModule,
    MatCheckboxModule,
    MatIconModule,
    MatGridListModule,
    MatButtonModule,
    MatTabsModule,
    MatDialogModule,
    SqlViewerDialogComponent,
    MatProgressSpinnerModule,
  ],
  templateUrl: './product-results.component.html',
  styleUrls: ['./product-results.component.scss'],
})
export class ProductResultsComponent implements OnInit, OnDestroy {
  constructor(
    private cdr: ChangeDetectorRef,
    private RoleService: RoleService,
    public dialog: MatDialog
  ) {}

  // --- Inputs for loading states ---
  @Input() productsLoading: boolean = false;
  @Input() facetsLoading: boolean = false;
  @Input() aiFilterEnabled?: boolean;

  // --- Property to store the interpolated query for display ---
  public interpolatedQuery?: string = undefined;
  public facetInterpolatedQuery?: string = undefined;

  // --- Properties to hold current and total counts --
  public productsDisplayedCount: number | undefined;
  public totalFacetItemsCount: number | undefined;

  // --- Inputs for search---
  @Input() searchQuery: string | undefined;
  @Input() searchType: string | undefined;

  // Use setters to handle observable inputs and subscriptions
  private productsSub: Subscription | undefined;
  @Input()
  set productsResponse(
    observable: Observable<QueryResponse<Product>> | undefined
  ) {
    this.productsSub?.unsubscribe(); // Unsubscribe from previous
    this.clearProductResults(); // Clear old data

    if (observable) {
      this.productsSub = observable
        .pipe(
          map(response => this.processProductResponse(response)) // Use map for transformation
        )
        .subscribe(processedResponse => {
          this.query = processedResponse.query;
          this.interpolatedQuery = processedResponse.interpolatedQuery;
          this.data = processedResponse.data;
          this.errorDetail = processedResponse.errorDetail;
          this.productsDisplayedCount = this.data?.length ?? 0;
          this.cdr.detectChanges();
        });
    }
  }

  private facetsSub: Subscription | undefined;
  @Input()
  set facetsResponse(observable: Observable<FacetResponse> | undefined) {
    this.facetsSub?.unsubscribe(); // Unsubscribe from previous
    this.expandedFacets = {}; // Reset facet expansion state

    if (observable) {
      // Always subscribe and process new facet data
      this.facetsSub = observable.subscribe(response => {
        this.facetInterpolatedQuery = response.query;
        this.totalFacetItemsCount = response.totalCount;
        console.log(`Total facet counts: ${this.totalFacetItemsCount}`);
        if (response.data) {
          this.processAndGroupFacets(response.data);
        } else if (response.errorDetail) {
          console.error('Error fetching facets:', response.errorDetail);
          this.groupedFacets = []; // Clear on error
          this.totalFacetItemsCount = undefined;
        } else {
          // Handle case where response has no data and no error (e.g., empty facets)
          this.groupedFacets = [];
          this.totalFacetItemsCount = 0;
        }
        // Checkboxes will automatically reflect the persisted `selectedFacets` state
        // against the newly rendered `groupedFacets` list.
        this.cdr.detectChanges();
      });
    } else {
      // Observable cleared (e.g., new search started in parent)
      this.clearAllFacetData();
      this.totalFacetItemsCount = undefined;
      this.cdr.detectChanges();
    }
  }

  // --- Component State ---
  public query?: string = undefined;
  data?: Product[] = undefined;
  generatedQuery?: string = undefined;
  errorDetail?: string = undefined;
  totalCount?: number | undefined = undefined;

  // Facet specific state
  groupedFacets: FacetGroup[] = []; // Array to hold grouped facets for the template
  selectedFacets: {[key: string]: string[]} = {}; // Persist the selected facet values { facetType: [value1, value2] }

  // --- Properties for facet expansion ---
  readonly INITIAL_FACET_COUNT = 5; // Number of facets to show initially
  expandedFacets: {[facetTypeKey: string]: boolean} = {}; // e.g., { 'brand': false, 'category': false }

  // --- Output event emitter ---
  @Output() facetSelectionChange = new EventEmitter<{
    [key: string]: string[];
  }>();

  ngOnInit(): void {}

  ngOnDestroy(): void {
    // Clean up subscriptions when the component is destroyed
    this.productsSub?.unsubscribe();
    this.facetsSub?.unsubscribe();
  }

  public clearProductResults(): void {
    this.data = undefined;
    this.query = undefined;
    this.errorDetail = undefined;
    this.interpolatedQuery = undefined;
    this.totalCount = undefined;
    this.productsDisplayedCount = undefined;
  }

  public clearAllFacetData(): void {
    this.groupedFacets = [];
    this.selectedFacets = {};
    this.expandedFacets = {};
    this.totalCount = undefined;
    this.totalFacetItemsCount = undefined;
    this.facetInterpolatedQuery = undefined;
  }

  // Process Product Data (extracted logic)
  private processProductResponse(
    response: QueryResponse<Product>
  ): QueryResponse<Product> {
    if (response.data && response.data.length > 0) {
      const modifiedData = response.data.map(product => {
        const modifiedProduct = {...product};
        if (
          modifiedProduct.productImageUri &&
          typeof modifiedProduct.productImageUri === 'string' &&
          modifiedProduct.productImageUri.startsWith('gs://')
        ) {
          modifiedProduct.productImageUri =
            modifiedProduct.productImageUri.replace(
              'gs://',
              'https://storage.cloud.google.com/'
            );
        }
        const decimalPlaces = 7;
        if (
          modifiedProduct.rrfScore !== null &&
          modifiedProduct.rrfScore !== undefined
        ) {
          const factor = Math.pow(10, decimalPlaces);
          modifiedProduct.rrfScore =
            Math.round(modifiedProduct.rrfScore * factor) / factor;
        }
        return modifiedProduct;
      });
      return {...response, data: modifiedData};
    }
    return response;
  }

  // Process and Group Facets
  private processAndGroupFacets(rawFacets: RawFacet[]): void {
    const facetMap = new Map<string, Facet[]>();

    rawFacets.forEach(facet => {
      const type = facet.facetType;
      if (!facetMap.has(type)) {
        facetMap.set(type, []);
      }
      facetMap.get(type)?.push({value: facet.facetValue, count: facet.count});
    });

    // Convert map to array for the template, maintaining desired order
    this.groupedFacets = [];
    const order = ['brand', 'category', 'price_range']; // Define desired order
    order.forEach(type => {
      if (facetMap.has(type)) {
        this.groupedFacets.push({
          type: this.formatFacetType(type),
          values: facetMap.get(type)!,
        });
      }
    });

    // Add any remaining types (in case new ones appear)
    facetMap.forEach((values, type) => {
      if (!order.includes(type)) {
        this.groupedFacets.push({type: this.formatFacetType(type), values});
      }
    });
  }

  // Helper to format facet type names for display
  formatFacetType(type: string): string {
    switch (type) {
      case 'brand':
        return 'Brand';
      case 'category':
        return 'Category';
      case 'price_range':
        return 'Price Range';
      default:
        return type.charAt(0).toUpperCase() + type.slice(1); // Capitalize first letter
    }
  }

  // Handle facet selection (checkbox click)
  onFacetChange(
    facetType: string,
    facetValue: string,
    isChecked: boolean
  ): void {
    const typeKey = facetType.toLowerCase().replace(/\s+/g, '_');

    // Initialize if necessary
    if (!this.selectedFacets[typeKey]) {
      this.selectedFacets[typeKey] = [];
    }

    // Update selection
    const index = this.selectedFacets[typeKey].indexOf(facetValue);
    if (isChecked && index === -1) {
      this.selectedFacets[typeKey].push(facetValue);
    } else if (!isChecked && index > -1) {
      this.selectedFacets[typeKey].splice(index, 1);
    }

    // Clean up empty type arrays
    if (this.selectedFacets[typeKey].length === 0) {
      delete this.selectedFacets[typeKey];
    }

    // --- Emit the updated selection object ---
    this.facetSelectionChange.emit(this.selectedFacets);
  }

  // Check if a specific facet value is currently selected
  isFacetSelected(facetType: string, facetValue: string): boolean {
    const typeKey = facetType.toLowerCase().replace(' ', '_');
    return this.selectedFacets[typeKey]?.includes(facetValue) ?? false;
  }

  /** Checks if a facet group should have a "Show more/less" button */
  isExpandable(group: FacetGroup): boolean {
    const groupTypeKey = group.type.toLowerCase();
    // *** CHANGE: Define which groups are expandable ***
    const expandableTypes = ['brand', 'category']; // Add 'category'
    return (
      expandableTypes.includes(groupTypeKey) &&
      group.values.length > this.INITIAL_FACET_COUNT
    );
  }

  /** Checks if a specific group type is currently expanded */
  isGroupExpanded(groupType: string): boolean {
    const groupTypeKey = groupType.toLowerCase();
    // Return the state from the map, default to false if not present
    return !!this.expandedFacets[groupTypeKey];
  }

  /** Toggles the expansion state for a given facet group type */
  toggleExpansion(groupType: string): void {
    const groupTypeKey = groupType.toLowerCase(); // Use lowercase key
    this.expandedFacets[groupTypeKey] = !this.isGroupExpanded(groupType); // Toggle state in map
    this.cdr.detectChanges(); // Trigger change detection
  }

  /** Gets the facets to display (sliced or full) based on expansion state */
  getSlicedFacets(group: FacetGroup): Facet[] {
    // Slice only if the group is expandable AND currently not expanded
    if (this.isExpandable(group) && !this.isGroupExpanded(group.type)) {
      return group.values.slice(0, this.INITIAL_FACET_COUNT);
    }
    return group.values; // Return all if not expandable or already expanded
  }

  // Add method to open the SQL query dialog
  public openSqlDialog(): void {
    // Only open if there's actually a query to show
    if (this.interpolatedQuery || this.query || this.facetInterpolatedQuery) {
      this.dialog.open(SqlViewerDialogComponent, {
        width: '85vw', // Set width to 85% of viewport width
        height: '85vh', // Set height to 85% of viewport height
        maxWidth: 'none', // Remove max width constraint if it interferes
        maxHeight: 'none', // Remove max height constraint if it interferes
        data: {
          // Pass the queries to the dialog component
          productQuery: this.interpolatedQuery
            ? this.interpolatedQuery
            : this.query,
          facetQuery: this.facetInterpolatedQuery,
        },
      });
    }
  }

  getColumns(obj: object) {
    return Object.keys(obj);
  }

  getRows(obj: object) {
    return Object.values(obj);
  }
}
