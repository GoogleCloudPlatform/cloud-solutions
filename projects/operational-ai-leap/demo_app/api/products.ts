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
  Database,
  camelCaseRows,
  safeString,
  SelectedFacets,
  interpolateQuery,
} from './database';

// Interface for the raw facet data from SQL
export interface RawFacet {
  facetValue: string;
  facetType: 'brand' | 'category' | 'price_range'; // Use specific types
  count: number;
}

// Interface for the structured facet response
export interface FacetGroup {
  type: string;
  values: {value: string; count: number}[];
}

// --- Helper Function for Price Range Conditions ---
// Translates facet string values ('$50 - $99.99') into SQL conditions
function buildPriceRangeCondition(priceRanges: string[] | undefined): string {
  if (!priceRanges || priceRanges.length === 0) {
    return ''; // No price condition
  }

  const conditions = priceRanges.map(range => {
    switch (range) {
      case '$0 - $49.99':
        return '(p.retail_price >= 0 AND p.retail_price < 50)';
      case '$50 - $99.99':
        return '(p.retail_price >= 50 AND p.retail_price < 100)';
      case '$100 - $249.99':
        return '(p.retail_price >= 100 AND p.retail_price < 250)';
      case '$250 - $499.99':
        return '(p.retail_price >= 250 AND p.retail_price < 500)';
      case '$500+':
        return '(p.retail_price >= 500)';
      default:
        console.warn(`Unknown price range facet value: ${range}`);
        return 'FALSE'; // Or handle unknown ranges differently
    }
  });

  // Combine multiple selected ranges with OR
  return `AND (${conditions.join(' OR ')})`;
}

// --- Helper Function for General Facet Conditions ---
function buildFacetCondition(
  paramIndexStart: number,
  facetType: 'brand' | 'category', // Add other types if needed
  values: string[] | undefined,
  sqlColumnName: string // e.g., 'p.brand', 'p.category'
): {clause: string; params: unknown[]; nextParamIndex: number} {
  if (!values || values.length === 0) {
    return {clause: '', params: [], nextParamIndex: paramIndexStart};
  }

  const paramPlaceholder = `$${paramIndexStart}`;
  const clause = `AND ${sqlColumnName} = ANY(${paramPlaceholder})`;
  const params = [values]; // Pass the array of selected values as a single parameter

  return {clause, params, nextParamIndex: paramIndexStart + 1};
}

// --- Helper Function to build the WHERE clause from selected facets ---
function buildFacetWhereClause(selectedFacets: SelectedFacets): {
  clause: string;
  params: unknown[];
} {
  const conditions: string[] = [];
  const queryParams: unknown[] = [];
  let paramIndex = 1; // Start parameter index at $1

  // Brand
  const brandCondition = buildFacetCondition(
    paramIndex,
    'brand',
    selectedFacets['brand'],
    'p.brand'
  );
  if (brandCondition.clause) {
    conditions.push(brandCondition.clause);
    queryParams.push(...brandCondition.params);
    paramIndex = brandCondition.nextParamIndex;
  }

  // Category
  const categoryCondition = buildFacetCondition(
    paramIndex,
    'category',
    selectedFacets['category'],
    'p.category'
  );
  if (categoryCondition.clause) {
    conditions.push(categoryCondition.clause);
    queryParams.push(...categoryCondition.params);
    paramIndex = categoryCondition.nextParamIndex;
  }

  // Price Range (handled separately as it doesn't use = ANY)
  const priceCondition = buildPriceRangeCondition(
    selectedFacets['price_range']
  );
  if (priceCondition) {
    conditions.push(priceCondition);
    // No parameters added for price range as it's built directly into the string
  }

  // Combine all conditions
  const whereClause = conditions.length > 0 ? conditions.join(' ') : '';

  return {clause: whereClause, params: queryParams};
}

// --- Helper Function to build candidate_ids CTE for facet query ---
function buildFacetCandidateSql(
  searchTerm: string,
  searchType: string,
  facetWhereClause: string
): string {
  const safeSearchTerm = safeString(searchTerm);
  let candidateSql = `
        candidate_ids AS (
    `;

  console.log('searchType: ' + searchType);

  switch (searchType) {
    case 'textEmbeddings':
      candidateSql += `
            WITH vs AS (
                    SELECT id, product_embedding <=> embedding('gemini-embedding-001', '${safeSearchTerm}')::vector AS distance
                    FROM products p
                    WHERE 1=1 ${facetWhereClause}
                    ORDER BY distance LIMIT 500
                ) SELECT id FROM vs WHERE distance < 0.5
            )
            `;
      break;
    case 'image':
      // 'searchTerm' here is the image URI
      candidateSql += `
            WITH image_embedding AS (
              SELECT ai.image_embedding(
                  model_id => 'multimodalembedding@001',
                  image => '${safeSearchTerm}',
                  mimetype => 'image/png'
              )::vector AS embedding
            ), distance_result AS (SELECT  p.id,
                    p.product_image_embedding <=>  image_embedding.embedding AS distance
                FROM products p, image_embedding
                WHERE p.product_image_embedding IS NOT NULL
                ORDER BY distance
                LIMIT 500
            ) SELECT id FROM distance_result WHERE distance < 0.6
            )
            `;
      break;
    case 'fulltext':
      candidateSql += `
                SELECT id FROM products WHERE fts_document @@ websearch_to_tsquery('english', '${safeSearchTerm}')
            )
            `;
      break;
    case 'traditionalSql': {
      const formattedSearchTerm = searchTerm
        .replace(/\s+/g, ' ')
        .split(' ')
        .join('%');
      candidateSql += `
                SELECT id FROM products WHERE name ILIKE '%${safeString(formattedSearchTerm)}%'
                 OR sku ILIKE '%${safeString(formattedSearchTerm)}%'
                 OR category ILIKE '%${safeString(formattedSearchTerm)}%'
                 OR brand ILIKE '%${safeString(formattedSearchTerm)}%'
                 OR department ILIKE '%${safeString(formattedSearchTerm)}%'
                 OR product_description ILIKE '%${safeString(formattedSearchTerm)}%'
                 )
            `;
      break;
    }
    case 'hybrid':
      candidateSql += `
                WITH e AS (
                    SELECT embedding('gemini-embedding-001', '${safeSearchTerm}')::vector AS query_embedding
                ),
                vector_candidates AS (
                    SELECT
                        p.id,
                        p.product_embedding <=> e.query_embedding AS distance
                    FROM products p, e
                    WHERE p.product_embedding <=> e.query_embedding < 0.5
                    ${facetWhereClause}
                    ORDER BY distance
                    LIMIT 500
                )
                SELECT id FROM vector_candidates
                UNION
                SELECT id FROM products WHERE sku = '${safeSearchTerm}'
                UNION
                SELECT id FROM products WHERE fts_document @@ websearch_to_tsquery('english', '${safeSearchTerm}')
            )
            `;
      break;
  }
  return candidateSql;
}

export class Products {
  constructor(private db: Database) {}

  async getFacets(
    searchTerm: string,
    searchType: string,
    selectedFacets?: SelectedFacets
  ): Promise<{
    data: RawFacet[];
    query: string;
    totalCount?: number;
    errorDetail?: string;
  }> {
    let queryTemplate;

    // Build the WHERE clause and parameters based on the *selected* facets
    const {clause: facetWhereClause, params: facetParams} =
      buildFacetWhereClause(selectedFacets ?? {});

    // Built the candidate sql
    const candidateSql = buildFacetCandidateSql(
      searchTerm,
      searchType,
      facetWhereClause
    ); // Build dynamic CTE based on search term/type

    try {
      queryTemplate = `
            WITH
              -- 1. Get candidates based on initial search term/type
              ${candidateSql},
              -- 2. Filter products based on BOTH candidates AND selected facets
              products_for_faceting AS (
                SELECT
                  p.id,
                  p.name,
                  p.product_description,
                  p.department,
                  p.brand,
                  p.category,
                  p.retail_price
                FROM
                  products AS p
                  JOIN candidate_ids AS c ON p.id = c.id
                WHERE 1=1 ${facetWhereClause}
              ),
              -- 3. Calculate the total count of items matching facet criteria
              facet_total_count AS (
                  SELECT COUNT(DISTINCT id) as total_facet_items FROM products_for_faceting
              ),
              -- 4. Create price range bins AFTER filtering
              products_with_price_range AS (
                 SELECT
                      pff.brand,
                      pff.category,
                      CASE
                        WHEN pff.retail_price < 50 THEN '$0 - $49.99'
                        WHEN pff.retail_price >= 50 AND pff.retail_price < 100 THEN '$50 - $99.99'
                        WHEN pff.retail_price >= 100 AND pff.retail_price < 250 THEN '$100 - $249.99'
                        WHEN pff.retail_price >= 250 AND pff.retail_price < 500 THEN '$250 - $499.99'
                        WHEN pff.retail_price >= 500 THEN '$500+'
                        ELSE NULL
                      END AS price_range,
                      pff.retail_price -- Keep for ordering price ranges
                 FROM products_for_faceting pff
              ),
              -- 5. Calculate Aggregations using GROUPING SETS on the filtered set
              facet_aggregations AS (
                SELECT
                  COALESCE(brand, category, price_range) AS facet_value,
                  CASE
                    WHEN GROUPING(brand) = 0 THEN 'brand'
                    WHEN GROUPING(category) = 0 THEN 'category'
                    WHEN GROUPING(price_range) = 0 THEN 'price_range'
                  END AS facet_type,
                  COUNT(*) AS count,
                  MIN(retail_price) as min_price_for_ordering
                FROM
                  products_with_price_range -- Use the filtered data WITH price ranges
                WHERE
                    brand IS NOT NULL OR category IS NOT NULL OR price_range IS NOT NULL
                GROUP BY
                  GROUPING SETS (
                    (brand),
                    (category),
                    (price_range)
                  )
              )
            -- 6. Final SELECT and ORDER BY from the aggregated results
            SELECT
              fa.facet_value,
              fa.facet_type,
              fa.count,
              (SELECT total_facet_items FROM facet_total_count) AS total_count
            FROM
              facet_aggregations fa
            ORDER BY
              facet_type ASC,
              CASE WHEN facet_type = 'price_range' THEN min_price_for_ordering ELSE NULL END ASC NULLS LAST,
              count DESC,
              facet_value ASC;
            `;

      // Execute with parameters for the facet filters
      const rows = (await this.db.queryWithParams(
        queryTemplate,
        facetParams
      )) as Record<string, unknown>[];

      let totalCount;
      // Extract totalCount if the column exists in the first row
      if (
        rows.length > 0 &&
        Object.prototype.hasOwnProperty.call(rows[0], 'total_count')
      ) {
        // Convert bigint from pg potentially returned as string
        totalCount = parseInt(rows[0]['total_count'] as string, 10);
      } else if (rows.length === 0) {
        totalCount = 0;
      }

      const typedRows = camelCaseRows(rows) as unknown as RawFacet[];
      // Generate interpolated query for debugging if needed
      const interpolatedQuery = interpolateQuery(queryTemplate, facetParams);
      // NOTE: We return the *interpolated* query here for facet debugging
      return {
        data: typedRows,
        query: interpolatedQuery,
        totalCount: totalCount,
      };
    } catch (error) {
      const errorDetail = `getFacets errored.\nSQL Template: ${queryTemplate?.substring(0, 500)}...\nParams: ${JSON.stringify(facetParams)}\nError: ${(error as Error)?.message}`;
      console.error(errorDetail);
      const displayQuery = queryTemplate
        ? interpolateQuery(queryTemplate, facetParams)
        : 'Query construction failed';
      return {
        data: [],
        query: displayQuery,
        errorDetail: errorDetail,
        totalCount: 0,
      };
    }
  }

  private async executeFinalQuery(
    finalQuery: string,
    params: unknown[],
    searchType: string,
    aiFilterText?: string
  ): Promise<{
    data: Record<string, unknown>[];
    query: string;
    interpolatedQuery: string;
    errorDetail?: string;
    searchType?: string;
    totalCount?: number;
  }> {
    const executedQuery = finalQuery; // Keep track of what was actually run
    let resultRows: Record<string, unknown>[] = [];
    let interpolatedQueryString: string | undefined = ''; // For display
    let totalCount: number | undefined = undefined;

    // --- Apply the Gemini filter (if enabled) to the smallest possible result set ---
    if (aiFilterText && aiFilterText.trim() !== '') {
      const safeAiFilter = safeString(aiFilterText.trim()); // Ensure text is SQL-safe
      finalQuery =
        'WITH pre_filtered_results AS (' +
        finalQuery +
        `)
                          SELECT * FROM pre_filtered_results
                          WHERE ai.if(prompt => 'The following product ${safeAiFilter}: ' ||
                                ' Product name: ' || COALESCE(name, '') ||
                                ' Brand: ' || COALESCE(brand, '') ||
                                ' Category: ' || COALESCE(category, '') ||
                                ' Department: ' || COALESCE(department, '') ||
                                ' Price: ' || COALESCE(retail_price, '') ||
                                ' Description: ' || COALESCE(product_description, ''))`;
    }

    try {
      interpolatedQueryString = interpolateQuery(finalQuery, params);

      const rows = (await this.db.queryWithParams(
        finalQuery,
        params
      )) as Record<string, unknown>[];
      resultRows = rows;

      // Extract totalCount if the column exists in the first row
      if (
        resultRows.length > 0 &&
        Object.prototype.hasOwnProperty.call(resultRows[0], 'total_count')
      ) {
        // Convert bigint from pg potentially returned as string
        totalCount = parseInt(resultRows[0]['total_count'] as string, 10);
      } else if (resultRows.length === 0) {
        totalCount = 0;
      }

      const finalData = resultRows.map(row => {
        const rowCopy = {...row};
        delete rowCopy['total_count'];
        return rowCopy;
      });

      return {
        data: camelCaseRows(finalData), // Apply camelCase to data without total_count
        query: executedQuery,
        interpolatedQuery: interpolatedQueryString,
        searchType: searchType,
        totalCount: totalCount,
      };
    } catch (error) {
      const errorDetail = `Error executing final query: ${interpolatedQueryString} \nParams: ${JSON.stringify(params)}\nError: ${(error as Error)?.message}`;
      console.error(errorDetail);
      return {
        data: [],
        query: executedQuery,
        interpolatedQuery: interpolatedQueryString || finalQuery,
        errorDetail: errorDetail,
        searchType: searchType,
        totalCount: undefined,
      };
    }
  }

  async search(
    term: string,
    selectedFacets?: SelectedFacets,
    aiFilterText?: string
  ) {
    const searchType = 'TRADITIONAL_SQL';
    const formattedSearchTerm = term.replace(/\s+/g, ' ').split(' ').join('%');
    const {clause: facetWhereClause, params: facetParams} =
      buildFacetWhereClause(selectedFacets ?? {});

    // Base query - use 'p' alias for products table
    const query = `
            SELECT
                p.name, p.product_image_uri, p.brand, p.product_description,
                p.category, p.department, p.cost, p.retail_price::MONEY, p.sku,
                'SQL' AS retrieval_method,
                COUNT(*) OVER () AS total_count
            FROM products p
            WHERE (name ILIKE '%${safeString(formattedSearchTerm)}%'
                OR sku ILIKE '%${safeString(formattedSearchTerm)}%'
                OR category ILIKE '%${safeString(formattedSearchTerm)}%'
                OR brand ILIKE '%${safeString(formattedSearchTerm)}%'
                OR department ILIKE '%${safeString(formattedSearchTerm)}%'
                OR product_description ILIKE '%${safeString(formattedSearchTerm)}%')
            ${facetWhereClause}
            ORDER BY name
            LIMIT 12`; // Consider if LIMIT should be applied before or after faceting

    // Note: This specific query uses ILIKE, making direct parameterization difficult.
    // For this example, we keep ILIKE and append the parameterized facet clause.
    return this.executeFinalQuery(query, facetParams, searchType, aiFilterText);
  }

  async fulltextSearch(
    term: string,
    selectedFacets?: SelectedFacets,
    aiFilterText?: string
  ) {
    const searchType = 'FULLTEXT';
    const {clause: facetWhereClause, params: facetParams} =
      buildFacetWhereClause(selectedFacets ?? {});
    const ftsQueryFunction = 'websearch_to_tsquery'; // Or plainto_tsquery
    const ftsQuery = `${ftsQueryFunction}('english', '${safeString(term)}')`;

    // Combine base parameters with facet parameters
    // Note: The FTS part itself is not parameterized here for simplicity, only facets are.
    const allParams = [...facetParams];

    const query = `
            SELECT
                ts_rank(p.fts_document, ${ftsQuery}) AS fts_rank_score,
                p.name, p.product_image_uri, p.brand, p.product_description,
                p.category, p.department, p.cost, p.retail_price::MONEY, p.sku,
                'FTS' AS retrieval_method,
                COUNT(*) OVER () AS total_count
            FROM products p
            WHERE p.fts_document @@ ${ftsQuery}
            ${facetWhereClause}
            ORDER BY fts_rank_score DESC
            LIMIT 12`;

    return this.executeFinalQuery(query, allParams, searchType, aiFilterText);
  }

  async semanticSearch(
    prompt: string,
    selectedFacets?: SelectedFacets,
    aiFilterText?: string
  ) {
    const searchType = 'SEMANTIC';
    const {clause: facetWhereClause, params: facetParams} =
      buildFacetWhereClause(selectedFacets ?? {});

    const embeddingFunction = `embedding('gemini-embedding-001', '${safeString(prompt)}')::vector`;
    const allParams = [...facetParams];

    const query = `
            WITH e AS (
                SELECT ${embeddingFunction} AS query_embedding
            ),
            vector_search AS (
                SELECT
                    p.id,
                    p.product_embedding <=> e.query_embedding AS distance
                FROM products p, e
                WHERE p.product_embedding <=> e.query_embedding < 0.5
                ${facetWhereClause}
                ORDER BY distance
                LIMIT 50
            )
            SELECT
                vs.distance,
                p.name, p.product_image_uri, p.brand, p.product_description,
                p.category, p.department, p.cost, p.retail_price::MONEY, p.sku,
                'VECTOR' AS retrieval_method
            FROM vector_search vs
            JOIN products p ON vs.id = p.id
            ORDER BY vs.distance
            LIMIT 24`;

    return this.executeFinalQuery(query, allParams, searchType, aiFilterText);
  }

  async hybridSearch(
    term: string,
    selectedFacets?: SelectedFacets,
    aiFilterText?: string
  ) {
    const searchType = 'HYBRID';
    const {clause: facetWhereClause, params: facetParams} =
      buildFacetWhereClause(selectedFacets ?? {});

    // Prepare terms safely
    const safeFtsTerm = safeString(term);
    const safeVectorTerm = safeString(
      term
        .replace(/\s+/g, ' ')
        .replace(/'+/g, '')
        .replace(/"+/g, '')
        .replace(/-+/g, '')
    );
    const safeSqlTerm = safeString(
      term.replace(/\s+/g, ' ').split(' ').join('%')
    ); // Basic transformation for SKU/ILIKE

    const limit = 24; // Final results limit
    const rrfK = 60; // K value for RRF ranking

    // Use placeholders in the query string and pass values via params array
    const query = `
            WITH trad_sql AS (
                SELECT RANK() OVER (ORDER BY name) AS trad_sql_rank, id FROM products WHERE sku = $${facetParams.length + 1} ORDER BY name
            ), fts_search AS (
                SELECT ts_rank(fts_document, websearch_to_tsquery('english', $${facetParams.length + 2})) AS score, RANK() OVER (ORDER BY ts_rank(fts_document, websearch_to_tsquery('english', $${facetParams.length + 2})) DESC) as rank, id
                FROM products WHERE fts_document @@ websearch_to_tsquery('english', $${facetParams.length + 2}) ORDER BY score DESC
            ), vector_search AS (
                WITH e AS (
                    SELECT embedding ('gemini-embedding-001', $${facetParams.length + 3})::vector AS query_embedding
                ),
                vs AS (
                    SELECT
                        p.id,
                        p.product_embedding <=> e.query_embedding AS distance
                    FROM products p, e
                    WHERE p.product_embedding <=> e.query_embedding < 0.5
                    ${facetWhereClause}
                    ORDER BY distance
                    LIMIT 50
                )
                SELECT
                    vs.id,
                    vs.distance,
                    RANK() OVER (ORDER BY distance) AS rank
                FROM vs
            ),
            -- Combine and rank
            combined_results AS (
                 SELECT
                    p.id, p.name, p.product_image_uri, p.brand, p.product_description, p.category, p.department, p.cost, p.retail_price, p.sku,
                    GREATEST( -- Boost SKU matches and vector search results
                      COALESCE( (1.0 / (${rrfK - 5} + vector_search.rank)), 0.0 ),
                      COALESCE( (1.0 / (${rrfK} + fts_search.rank)), 0.0 ),
                      COALESCE( (1.0 / (${rrfK - 10} + trad_sql.trad_sql_rank)), 0.0 )
                    ) AS rrf_score,
                    CONCAT_WS( '+',
                        CASE WHEN vector_search.rank IS NOT NULL THEN 'VECTOR' ELSE NULL END,
                        CASE WHEN fts_search.rank IS NOT NULL THEN 'FTS' ELSE NULL END,
                        CASE WHEN trad_sql.trad_sql_rank IS NOT NULL THEN 'SQL' ELSE NULL END
                    ) AS retrieval_method,
                    COUNT(*) OVER () as total_count
                FROM products p
                LEFT JOIN vector_search ON p.id = vector_search.id
                LEFT JOIN fts_search ON p.id = fts_search.id
                LEFT JOIN trad_sql ON p.id = trad_sql.id
                WHERE (vector_search.id IS NOT NULL OR fts_search.id IS NOT NULL OR trad_sql.id IS NOT NULL)
                ${facetWhereClause}
            )
            -- Final Selection
            SELECT id, name, product_image_uri, brand, product_description, category, department, cost, retail_price::MONEY, sku, rrf_score, retrieval_method, total_count
            FROM combined_results
            ORDER BY rrf_score DESC
            LIMIT ${limit}
            `;

    // Combine facet parameters with the query-specific parameters
    const allParams = [
      ...facetParams,
      safeSqlTerm,
      safeFtsTerm,
      safeVectorTerm,
    ];

    return this.executeFinalQuery(query, allParams, searchType, aiFilterText);
  }

  async imageSearch(
    searchUri: string,
    selectedFacets?: SelectedFacets,
    aiFilterText?: string
  ) {
    let query;
    const searchType = 'IMAGE';
    const limit = 12; // Final limit after filtering

    // Build the facet WHERE clause and get parameters
    const {clause: facetWhereClause, params: facetParams} =
      buildFacetWhereClause(selectedFacets ?? {});

    try {
      console.log(
        'Image search for:',
        searchUri,
        'with facets:',
        selectedFacets
      );
      query = `
                WITH image_embedding AS (
                    SELECT ai.image_embedding(
                        model_id => 'multimodalembedding@001',
                        image => '${safeString(searchUri)}',
                        mimetype => 'image/png')::vector AS embedding
                ), multimodal_candidates AS (
                    -- Find initial candidates based purely on image similarity
                    SELECT
                        p.id,
                        (p.product_image_embedding <=> ie.embedding) AS distance
                    FROM products p, image_embedding ie
                    WHERE p.product_image_embedding IS NOT NULL
                    ORDER BY distance
                    LIMIT 500
                ),
                -- Join candidates with product details and apply facet filters
                filtered_candidates AS (
                     SELECT
                        mc.id,
                        mc.distance
                    FROM multimodal_candidates mc
                    JOIN products p ON mc.id = p.id
                    WHERE distance < 0.6
                    ${facetWhereClause}
                    -- Parameters for facets will be passed to the final execution
                )
                -- Final selection and ranking
                SELECT
                    RANK () OVER (ORDER BY fc.distance) AS vector_rank,
                    p.id, p.name, p.product_image_uri, p.brand, p.product_description,
                    p.category, p.department, p.cost, p.retail_price::MONEY, p.sku,
                    'IMAGE' as retrieval_method, COUNT(*) OVER () as total_count
                FROM filtered_candidates fc
                JOIN products p ON fc.id = p.id
                ORDER BY fc.distance
                LIMIT ${limit}`;

      // Execute the query with facet parameters
      return this.executeFinalQuery(
        query,
        facetParams,
        searchType,
        aiFilterText
      );
    } catch (error) {
      const errorDetail = `imageSearch errored with query fragment: ${query?.substring(0, 200)}...\nError: ${(error as Error)?.message}`;
      console.error(errorDetail);
      return {
        data: [],
        query: query ?? 'Query construction failed',
        errorDetail: errorDetail,
        searchType: searchType,
      };
    }
  }

  async explainQuery(queryString: string) {
    const explainString: string = 'EXPLAIN ANALYZE ' + queryString;
    return this.executeFinalQuery(explainString, [], 'explain');
  }
}
