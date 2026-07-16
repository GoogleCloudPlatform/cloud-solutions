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

import {Component, Output, EventEmitter} from '@angular/core';
import {CommonModule} from '@angular/common'; // Import CommonModule for *ngFor, [ngClass] etc.
import {MatCardModule} from '@angular/material/card';

// Interface for clarity (optional but recommended)
interface SelectableImage {
  id: number; // Or any unique identifier
  uri: string;
  url: string;
  alt: string;
}

@Component({
  selector: 'app-image-selector',
  standalone: true,
  imports: [
    CommonModule, // <-- Import here for standalone component
    MatCardModule,
  ],
  templateUrl: './image-selector.component.html',
  styleUrls: ['./image-selector.component.scss'],
})
export class ImageSelectorComponent {
  images: SelectableImage[] = [
    {
      id: 3,
      uri: 'gs://sample-data-and-media/ecomm-retail/product-images-generic/621765159EE1EA4299C0DF3E1D29034B.png',
      url: 'https://storage.cloud.google.com/sample-data-and-media/ecomm-retail/product-images-generic/621765159EE1EA4299C0DF3E1D29034B.png',
      alt: 'Black Coat',
    },
    {
      id: 4,
      uri: 'gs://sample-data-and-media/ecomm-retail/product-images-generic/62343FE688D3B70314B5C1730328A936.png',
      url: 'https://storage.cloud.google.com/sample-data-and-media/ecomm-retail/product-images-generic/62343FE688D3B70314B5C1730328A936.png',
      alt: 'Gray Puffer Jacket',
    },
    {
      id: 5,
      uri: 'gs://sample-data-and-media/ecomm-retail/product-images-generic/0F975E34D0DBA01FEAC553CB9DD64857.png',
      url: 'https://storage.cloud.google.com/sample-data-and-media/ecomm-retail/product-images-generic/0F975E34D0DBA01FEAC553CB9DD64857.png',
      alt: 'Knit Hat',
    },
  ];

  // Variable to store the URI of the selected image
  selectedImageUri: string | null = null; // Initialize to null or undefined

  // Define the Output property
  @Output() imageSelected = new EventEmitter<string>(); // Will emit the selected string URI

  // Method called when an image container is clicked
  selectImage(imageUri: string): void {
    this.selectedImageUri = imageUri; // Update internal state (for highlighting)

    // Emit the selected URI to the parent component
    this.imageSelected.emit(this.selectedImageUri);
  }
}
