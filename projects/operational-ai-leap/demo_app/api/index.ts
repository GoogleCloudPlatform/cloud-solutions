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

import express from 'express';
import cors from 'cors';
import {join} from 'path';

import {Database, SelectedFacets} from './database';
import {Products} from './products';

//
// Create the express app
//
const app: express.Application = express();
const db: Database = new Database();
const products = new Products(db);
const staticPath = join(__dirname, 'ui/dist/cymbal-shops-ui/browser');

//
// Use middleware
//
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({extended: true}));
app.use(express.static(staticPath));

//
// Helper to parse facets and AI filter text
//
const parseSearchParams = (
  req: express.Request
): {
  term: string;
  selectedFacets: SelectedFacets;
  aiFilterText?: string;
  searchUri?: string;
  prompt?: string;
} => {
  const term: string = (req.query.term as string) ?? '';
  const searchUri: string = (req.query.searchUri as string) ?? '';
  const prompt: string = (req.query.prompt as string) ?? '';
  const selectedFacets = parseFacets(req.query.facets as string | undefined);
  const aiFilterText = req.query.aiFilterText as string | undefined; // Get the AI filter text
  return {term, selectedFacets, aiFilterText, searchUri, prompt};
};

//
// Helper to parse facets safely
//
const parseFacets = (facetsParam: string | undefined): SelectedFacets => {
  //console.log(`Facets: ${facetsParam}`)
  if (!facetsParam) return {};
  try {
    const parsed = JSON.parse(facetsParam);
    // Basic validation: check if it's an object
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      !Array.isArray(parsed)
    ) {
      // Further validation could be added here to ensure keys/values are correct types
      return parsed;
    }
    console.warn('Invalid facets parameter format:', facetsParam);
    return {};
  } catch (e) {
    console.warn('Could not parse facets parameter JSON:', facetsParam, e);
    return {};
  }
};

//
// Setup routes
//

/** Get facets for a search term AND type
 * i.e. /api/products/facets?term=sunglasses&searchType=hybrid
 */
app.get(
  '/api/products/facets',
  async (req: express.Request, res: express.Response) => {
    try {
      const term: string = (req.query.term as string) ?? '';
      const searchType: string = (req.query.searchType as string) ?? 'hybrid';
      const selectedFacets = parseFacets(
        req.query.facets as string | undefined
      );

      const response = await products.getFacets(
        term,
        searchType,
        selectedFacets
      );
      res.json(response);
    } catch (err) {
      console.error('error occurred fetching facets:', err);
      res.status(500).send(err);
    }
  }
);

app.get(
  '/api/products/search',
  async (req: express.Request, res: express.Response) => {
    try {
      const {term, selectedFacets, aiFilterText} = parseSearchParams(req);
      const response = await products.search(
        term,
        selectedFacets,
        aiFilterText
      ); // Pass aiFilterText
      res.json(response);
    } catch (err) {
      console.error('error occurred in basic search:', err);
      res.status(500).send(err);
    }
  }
);

app.get(
  '/api/products/fulltext-search',
  async (req: express.Request, res: express.Response) => {
    //console.log(`Facets before parse: ${req.query.facets}`)
    try {
      const {term, selectedFacets, aiFilterText} = parseSearchParams(req);
      const response = await products.fulltextSearch(
        term,
        selectedFacets,
        aiFilterText
      ); // Pass aiFilterText
      res.json(response);
    } catch (err) {
      console.error('error occurred in fulltext search:', err);
      res.status(500).send(err);
    }
  }
);

app.get(
  '/api/products/semantic-search',
  async (req: express.Request, res: express.Response) => {
    try {
      const {prompt, selectedFacets, aiFilterText} = parseSearchParams(req);
      const response = await products.semanticSearch(
        prompt!,
        selectedFacets,
        aiFilterText
      ); // Pass aiFilterText
      res.json(response);
    } catch (err) {
      console.error('error occurred in semantic search:', err);
      res.status(500).send(err);
    }
  }
);

app.get(
  '/api/products/hybrid-search',
  async (req: express.Request, res: express.Response) => {
    try {
      const {term, selectedFacets, aiFilterText} = parseSearchParams(req);
      const response = await products.hybridSearch(
        term,
        selectedFacets,
        aiFilterText
      ); // Pass aiFilterText
      res.json(response);
    } catch (err) {
      console.error('error occurred in hybrid search:', err);
      res.status(500).send(err);
    }
  }
);

/** Find products by image uri */
app.get(
  '/api/products/image-search',
  async (req: express.Request, res: express.Response) => {
    try {
      const {searchUri, selectedFacets, aiFilterText} = parseSearchParams(req);
      const response = await products.imageSearch(
        searchUri!,
        selectedFacets,
        aiFilterText
      ); // Pass aiFilterText
      res.json(response);
    } catch (err) {
      console.error('error occurred during image search:', err);
      res.status(500).send(err);
    }
  }
);

/** Explain Query Plan */
app.get(
  '/api/products/explain-query',
  async (req: express.Request, res: express.Response) => {
    try {
      const queryString: string = (req.query.queryString as string) ?? '';

      // Pass selectedFacets to the service method
      const response = await products.explainQuery(queryString);
      res.json(response);
    } catch (err) {
      console.error('error occurred during image search:', err);
      res.status(500).send(err);
    }
  }
);

/** Send any other request just to the products page
 */
app.get('*', (req, res) => {
  // Check if the request looks like an API call or a static file request first
  if (req.path.startsWith('/api/') || req.path.includes('.')) {
    // If it looks like an API call or a file request that wasn't found by express.static,
    // let it fall through (or send a 404 explicitly if preferred)
    res.status(404).send('Not Found');
  } else {
    // Otherwise, serve the main Angular index file
    res.sendFile(join(staticPath, 'index.html'));
  }
});

//
// Start the server
//
const port: number = parseInt(process.env.PORT ?? '8080');

app.listen(port, () => {
  console.log(`Cymbal Shops API: listening on port ${port}`);
});
