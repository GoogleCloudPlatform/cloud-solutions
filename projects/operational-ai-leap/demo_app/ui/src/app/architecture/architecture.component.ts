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

import {Component} from '@angular/core';
import {CommonModule} from '@angular/common'; // Import CommonModule for *ngFor
import {MatTableModule} from '@angular/material/table'; // Import MatTableModule
import {MatCardModule} from '@angular/material/card'; // Optional: for wrapping

// Interface for structuring the data
export interface SearchMethodComparison {
  methodName: string;
  strengths: string[];
  weaknesses: string[];
}

@Component({
  selector: 'app-architecture',
  standalone: true,
  imports: [
    CommonModule, // Needed for *ngFor
    MatTableModule, // <-- Import the Angular Material Table module
    MatCardModule, // <-- Optional card wrapper
  ],
  templateUrl: './architecture.component.html',
  styleUrls: ['./architecture.component.scss'],
})
export class ArchitectureComponent {
  // Data for the table
  comparisonData: SearchMethodComparison[] = [
    {
      methodName: 'Traditional SQL',
      strengths: [
        "Simple to implement for basic keyword checks (`=` or `ILIKE 'term%'`).",
        'Fast for exact matches on indexed fields (e.g., SKU, exact name).',
        'Easily integrates with strict attribute filtering (price, category, brand) via `WHERE` clause.',
        'Low infrastructure overhead beyond the primary database.',
      ],
      weaknesses: [
        'No relevance ranking; no understanding of user intent, synonyms, context, or semantics.',
        'Very sensitive to typos, pluralization, and phrasing variations.',
        "`ILIKE '%term%'` queries are slow and don't scale well.", // Escaped quote
        'Struggles with matching within long descriptions or multiple fields effectively.',
        'Requires users to know specific terms.',
      ],
    },
    {
      methodName: 'Full-Text Search',
      strengths: [
        "Faster keyword search than `ILIKE '%term%'` using inverted indexes.", // Escaped quote
        'Handles basic linguistic variations (stemming, stop words).',
        'Provides basic relevance ranking (e.g., TF-IDF).',
        'Can search across multiple text fields efficiently.',
        'Mature technology, often built into databases (PostgreSQL, SQL Server, etc.) or search engines (Elasticsearch, OpenSearch).',
      ],
      weaknesses: [
        'Primarily keyword-based; limited understanding of semantic meaning or user intent.',
        'Relevance can be hard to tune effectively.',
        'Struggles with complex synonyms or conceptual relationships unless explicitly configured.',
        'Does not handle natural language queries well.',
        'May return irrelevant results if keywords appear out of context.',
      ],
    },
    {
      methodName: 'Text Embeddings',
      strengths: [
        'Excellent semantic understanding; finds relevant products based on meaning, even with different keywords.',
        'Handles synonyms, paraphrasing, and natural language queries effectively.',
        'Good for discovery and finding conceptually similar items.',
        'Strong zero-shot capability (handles unseen queries/products if concepts overlap).',
      ],
      weaknesses: [
        'Can struggle with precise keyword matching (e.g., finding a specific model number if semantic similarity is low).',
        'Requires generating embeddings (ML model inference - compute cost).',
        'Needs specialized vector database or index (e.g., using ANN algorithms like ScaNN, HNSW) for efficient search at scale.',
        'Can sometimes return results that are *too* broad or conceptually related but functionally wrong.',
      ],
    },
    {
      methodName: 'Hybrid Search',
      strengths: [
        'Combines keyword precision (SQL/FTS) with semantic understanding (Embeddings).',
        'Generally provides the highest overall relevance across diverse query types.',
        'Robust to keyword-heavy queries, natural language, typos (via FTS), and conceptual search (via embeddings).',
        'Mitigates the weaknesses of using either keyword or semantic search alone.',
        'Techniques like Reciprocal Rank Fusion (RRF) allow effective merging of results.',
      ],
      weaknesses: [
        'Most complex to implement, tune, and maintain (requires managing/scaling both FTS and Vector indexes).',
        'Higher infrastructure costs and operational overhead.',
        'Requires careful tuning of the result merging/ranking strategy (e.g., weights, fusion algorithm).',
        'Potential for slightly increased query latency if not optimized well.',
      ],
    },
    {
      methodName: 'Image Search',
      strengths: [
        'Enables search based on visual similarity ("shop the look", finding alternatives).',
        "Doesn't rely on text descriptions; useful for products with poor or missing text data.",
        'Allows users to search using an uploaded image.',
        'Can identify products even with variations in angle or background (depending on model robustness).',
        'Can potentially be combined with text using multi-modal models.',
      ],
      weaknesses: [
        "Relevance is purely visual; may not match user's functional need or textual query intent.",
        'Requires image embedding generation, storage, and vector search infrastructure.',
        'Sensitive to image quality, lighting, and obstructions.',
        'Difficult to combine directly with keyword search or precise attribute filters unless using advanced multi-modal models.',
        'Can be computationally expensive (embedding generation and search).',
      ],
    },
  ];

  // Columns to display in the table, matching matColumnDef names
  displayedColumns: string[] = ['methodName', 'strengths', 'weaknesses'];

  // Assign the data to the dataSource input for the table
  dataSource = this.comparisonData;

  // You could wrap dataSource with MatTableDataSource for sorting/filtering features:
  // dataSource = new MatTableDataSource(this.comparisonData);

  // Get current date/time for display
  currentDateTime = new Date();
}
