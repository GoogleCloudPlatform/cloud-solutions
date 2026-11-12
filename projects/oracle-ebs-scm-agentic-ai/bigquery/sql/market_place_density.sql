-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     https://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- =============================================================================
-- VoltGuard market place density
-- Dataset: `your-project-id.ebs_scm_agentic_ai`
--
-- Counts the operational places that pull backup power demand forward in
-- every H3 cell (resolution 7, about 5 square kilometers) whose center lies
-- in a hub's 15 km market area, with the Places Insights PLACES_COUNT_PER_H3
-- function. The place groups match the zone demand exposure: critical care,
-- food retail, and hardware retail, by primary type. The density score
-- scales each cell's place count from 0 to 10 across the hub's cells for the
-- heatmap.
-- =============================================================================

DECLARE market_areas GEOGRAPHY DEFAULT (
    SELECT ST_UNION_AGG(ST_BUFFER(ST_GEOGPOINT(longitude, latitude), 15000))
    FROM `your-project-id.ebs_scm_agentic_ai.hub_market_areas`
);

CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.market_place_density` AS
WITH cell_counts AS (
    SELECT
        'critical_care' AS place_group,
        h3_cell_index,
        geography,
        count AS place_count
    FROM
        `your-project-id.places_insights___us.PLACES_COUNT_PER_H3`(
            JSON_OBJECT(
                'geography', market_areas,
                'primary_type',
                ['hospital', 'medical_lab', 'pharmacy', 'drugstore'],
                'business_status', ['OPERATIONAL'],
                'h3_resolution', 7
            )
        )
    UNION ALL
    SELECT
        'food_retail' AS place_group,
        h3_cell_index,
        geography,
        count AS place_count
    FROM
        `your-project-id.places_insights___us.PLACES_COUNT_PER_H3`(
            JSON_OBJECT(
                'geography', market_areas,
                'primary_type', ['grocery_store', 'supermarket'],
                'business_status', ['OPERATIONAL'],
                'h3_resolution', 7
            )
        )
    UNION ALL
    SELECT
        'hardware_retail' AS place_group,
        h3_cell_index,
        geography,
        count AS place_count
    FROM
        `your-project-id.places_insights___us.PLACES_COUNT_PER_H3`(
            JSON_OBJECT(
                'geography', market_areas,
                'primary_type', ['hardware_store', 'home_improvement_store'],
                'business_status', ['OPERATIONAL'],
                'h3_resolution', 7
            )
        )
),
cells AS (
    SELECT
        h3_cell_index,
        ST_CENTROID(ANY_VALUE(geography)) AS center,
        SUM(IF(place_group = 'critical_care', place_count, 0))
            AS critical_care_sites,
        SUM(IF(place_group = 'food_retail', place_count, 0))
            AS food_retail_sites,
        SUM(IF(place_group = 'hardware_retail', place_count, 0))
            AS hardware_retail_sites,
        SUM(place_count) AS place_count
    FROM
        cell_counts
    GROUP BY
        h3_cell_index
),
hub_cells AS (
    SELECT
        h.organization_code,
        h.hub_name,
        15.0 AS market_radius_km,
        c.h3_cell_index,
        ROUND(ST_Y(c.center), 6) AS latitude,
        ROUND(ST_X(c.center), 6) AS longitude,
        ROUND(
            ST_DISTANCE(c.center, ST_GEOGPOINT(h.longitude, h.latitude))
            / 1000,
            1
        ) AS distance_km,
        c.critical_care_sites,
        c.food_retail_sites,
        c.hardware_retail_sites,
        c.place_count
    FROM
        cells c
        INNER JOIN `your-project-id.ebs_scm_agentic_ai.hub_market_areas` h
            ON ST_DWITHIN(
                c.center, ST_GEOGPOINT(h.longitude, h.latitude), 15000
            )
)
SELECT
    *,
    ROUND(
        10 * SAFE_DIVIDE(
            place_count,
            MAX(place_count) OVER (PARTITION BY organization_code)
        ),
        1
    ) AS density_score,
    RANK() OVER (
        PARTITION BY organization_code ORDER BY place_count DESC
    ) AS density_rank,
    CURRENT_TIMESTAMP() AS refreshed_at
FROM
    hub_cells;
