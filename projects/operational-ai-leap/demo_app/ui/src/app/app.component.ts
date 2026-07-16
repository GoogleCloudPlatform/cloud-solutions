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

import {Component, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {RouterOutlet} from '@angular/router';
import {RouterModule} from '@angular/router';
import {BreakpointObserver, Breakpoints} from '@angular/cdk/layout';

import {MatButtonModule} from '@angular/material/button';
import {MatToolbarModule} from '@angular/material/toolbar';
import {MatIconModule} from '@angular/material/icon';

import {ProductsComponent} from './products/products.component';
import {SnackBarErrorComponent} from './common/SnackBarErrorComponent';

import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatDividerModule} from '@angular/material/divider';

import {MatMenuModule} from '@angular/material/menu';

import {RoleService} from './services/cymbalshops-api';

import {MatDialog} from '@angular/material/dialog';
import {MarkdownViewerComponent} from './common/markdown-viewer/markdown-viewer.component';
import {HttpClient} from '@angular/common/http';

import {ArchitectureComponent} from './architecture/architecture.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterModule,
    MatButtonModule,
    MatToolbarModule,
    MatIconModule,
    ProductsComponent,
    MatButtonToggleModule,
    MatCheckboxModule,
    MatDividerModule,
    MatMenuModule,
    MarkdownViewerComponent,
    ArchitectureComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  providers: [SnackBarErrorComponent],
})
export class AppComponent implements OnInit {
  constructor(
    private breakpointObserver: BreakpointObserver,
    private RoleService: RoleService,
    public dialog: MatDialog,
    private http: HttpClient
  ) {}

  isSmallScreen: boolean = false;

  markdownContent = '';

  ngOnInit() {
    this.breakpointObserver
      .observe([Breakpoints.Handset])
      .subscribe(
        () =>
          (this.isSmallScreen = this.breakpointObserver.isMatched(
            Breakpoints.Handset
          ))
      );
  }

  openArchitectureDialog() {
    this.dialog.open(ArchitectureComponent, {
      height: '90%',
      width: '90%',
    });
  }
}
