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
-- VoltGuard distribution zones
-- Dataset: `your-project-id.ebs_scm_agentic_ai`
--
-- Every hub serves the residential ZIP codes whose interior point lies within
-- its 15 km market area. Housing comes from the US Census Bureau American
-- Community Survey 2020 5-year estimates (the newest ZIP code tabulation area
-- vintage in the BigQuery public dataset), so a ZIP code without Census
-- housing estimates, such as a PO box or single-building ZIP code, is not a
-- distribution zone. zone_demand_exposure.sql counts the Google Maps places
-- inside each zone boundary with Places Insights.
-- =============================================================================

CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.distribution_zones` AS
SELECT
    h.organization_code,
    h.hub_name,
    15.0 AS market_radius_km,
    z.zip_code AS zone_id,
    TRIM(CONCAT(
        IFNULL(
            REGEXP_REPLACE(
                z.city, r' (city|CDP|town|village|borough|township)$', ''
            ),
            ''
        ),
        ' ',
        z.zip_code
    )) AS zone_name,
    z.internal_point_lat AS latitude,
    z.internal_point_lon AS longitude,
    ROUND(
        ST_DISTANCE(
            z.internal_point_geom, ST_GEOGPOINT(h.longitude, h.latitude)
        ) / 1000,
        1
    ) AS distance_km,
    CAST(a.housing_units AS INT64) AS housing_units,
    CAST(a.owner_occupied_housing_units AS INT64) AS owner_occupied_homes,
    -- Zone boundary simplified to 50 m.
    ST_SIMPLIFY(z.zip_code_geom, 50) AS zone_geom
FROM
    `your-project-id.ebs_scm_agentic_ai.hub_market_areas` h
    INNER JOIN `bigquery-public-data.geo_us_boundaries.zip_codes` z
        ON ST_DWITHIN(
            z.internal_point_geom, ST_GEOGPOINT(h.longitude, h.latitude), 15000
        )
    INNER JOIN `bigquery-public-data.census_bureau_acs.zcta_2020_5yr` a
        ON a.geo_id = z.zip_code
WHERE
    a.housing_units IS NOT NULL
    AND a.owner_occupied_housing_units IS NOT NULL;
