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
-- VoltGuard zone demand exposure
-- Dataset: `your-project-id.ebs_scm_agentic_ai`
--
-- Scores each hub's distribution zones by the places and homes that pull
-- backup power demand forward during a grid event:
--
--   * Critical care (hospitals, medical labs, pharmacies) 35%, food retail
--     (grocery stores, supermarkets) 20%, and hardware retail (hardware and
--     home improvement stores) 15%: operational places by primary type, from
--     the Places Insights PLACES_COUNT_V2 function.
--   * Owner-occupied homes 30%, from the US Census Bureau.
--
-- The query scales each component from 0 to 1 across the hub's zones, so the
-- 0 to 10 exposure score ranks zones within a hub. Gemini (AI.GENERATE) adds a
-- pull-forward tier and a one-sentence reason from the same facts and the
-- hub's demand driver. It runs through the voltguard_gemini BigQuery
-- connection, as that connection's service account. The score itself comes
-- only from SQL.
-- =============================================================================

CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.zone_demand_exposure` AS
WITH zones AS (
    SELECT
        CONCAT(organization_code, ':', zone_id) AS geo_id,
        zone_geom AS geo
    FROM
        `your-project-id.ebs_scm_agentic_ai.distribution_zones`
),
critical_care AS (
    SELECT geo_id, place_count
    FROM
        `your-project-id.places_insights___us.PLACES_COUNT_V2`(
            (SELECT geo_id, geo FROM zones),
            JSON '''{"primary_type": ["hospital", "medical_lab", "pharmacy",
                "drugstore"], "business_status": ["OPERATIONAL"]}'''
        )
),
food_retail AS (
    SELECT geo_id, place_count
    FROM
        `your-project-id.places_insights___us.PLACES_COUNT_V2`(
            (SELECT geo_id, geo FROM zones),
            JSON '''{"primary_type": ["grocery_store", "supermarket"],
                "business_status": ["OPERATIONAL"]}'''
        )
),
hardware_retail AS (
    SELECT geo_id, place_count
    FROM
        `your-project-id.places_insights___us.PLACES_COUNT_V2`(
            (SELECT geo_id, geo FROM zones),
            JSON '''{"primary_type": ["hardware_store",
                "home_improvement_store"], "business_status": ["OPERATIONAL"]}'''
        )
),
scaled AS (
    SELECT
        z.organization_code,
        z.hub_name,
        z.zone_id,
        z.zone_name,
        z.latitude,
        z.longitude,
        z.distance_km,
        z.market_radius_km,
        z.housing_units,
        z.owner_occupied_homes,
        c.place_count AS critical_care_sites,
        f.place_count AS food_retail_sites,
        w.place_count AS hardware_retail_sites,
        IFNULL(SAFE_DIVIDE(
            c.place_count - MIN(c.place_count) OVER hub,
            MAX(c.place_count) OVER hub - MIN(c.place_count) OVER hub
        ), 0) AS critical_care_index,
        IFNULL(SAFE_DIVIDE(
            f.place_count - MIN(f.place_count) OVER hub,
            MAX(f.place_count) OVER hub - MIN(f.place_count) OVER hub
        ), 0) AS food_retail_index,
        IFNULL(SAFE_DIVIDE(
            w.place_count - MIN(w.place_count) OVER hub,
            MAX(w.place_count) OVER hub - MIN(w.place_count) OVER hub
        ), 0) AS hardware_retail_index,
        IFNULL(SAFE_DIVIDE(
            z.owner_occupied_homes - MIN(z.owner_occupied_homes) OVER hub,
            MAX(z.owner_occupied_homes) OVER hub
            - MIN(z.owner_occupied_homes) OVER hub
        ), 0) AS homes_index
    FROM
        `your-project-id.ebs_scm_agentic_ai.distribution_zones` z
        INNER JOIN critical_care c
            ON c.geo_id = CONCAT(z.organization_code, ':', z.zone_id)
        INNER JOIN food_retail f
            ON f.geo_id = c.geo_id
        INNER JOIN hardware_retail w
            ON w.geo_id = c.geo_id
    WINDOW hub AS (PARTITION BY z.organization_code)
),
scored AS (
    SELECT
        *,
        CASE
            WHEN critical_care_index >= 2 / 3 THEN 'HIGH'
            WHEN critical_care_index >= 1 / 3 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS critical_care_level,
        CASE
            WHEN food_retail_index >= 2 / 3 THEN 'HIGH'
            WHEN food_retail_index >= 1 / 3 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS food_retail_level,
        CASE
            WHEN hardware_retail_index >= 2 / 3 THEN 'HIGH'
            WHEN hardware_retail_index >= 1 / 3 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS hardware_retail_level,
        ROUND(
            10 * (
                0.35 * critical_care_index
                + 0.20 * food_retail_index
                + 0.15 * hardware_retail_index
                + 0.30 * homes_index
            ),
            1
        ) AS exposure_score
    FROM
        scaled
),
drivers AS (
    SELECT
        organization_code,
        ARRAY_AGG(
            demand_driver_summary IGNORE NULLS
            ORDER BY search_percent_gain DESC
            LIMIT 1
        )[SAFE_OFFSET(0)] AS demand_driver
    FROM
        `your-project-id.ebs_scm_agentic_ai.regional_search_trends_surge`
    GROUP BY
        organization_code
),
assessed AS (
    SELECT
        s.*,
        AI.GENERATE(
            FORMAT(
                """You are a supply chain analyst for a backup generator distributor.
Assess how strongly the ZIP code zone %s, %.1f km from %s, pulls backup
generator demand forward during a grid event.
Compared with the hub's other zones, the zone's %d critical care sites are %s,
its %d food retail sites are %s, and its %d hardware retail sites are %s.
The zone has %d owner-occupied homes.
Its demand exposure score is %.1f out of 10.
Hub demand driver: %s.
Return pull_forward_tier as HIGH, MEDIUM, or LOW, and reasoning as one plain
sentence that uses only these facts.""",
                s.zone_name,
                s.distance_km,
                s.hub_name,
                s.critical_care_sites,
                LOWER(s.critical_care_level),
                s.food_retail_sites,
                LOWER(s.food_retail_level),
                s.hardware_retail_sites,
                LOWER(s.hardware_retail_level),
                s.owner_occupied_homes,
                s.exposure_score,
                IFNULL(d.demand_driver, 'none reported this week')
            ),
            connection_id => 'your-project-id.your-bigquery-location.voltguard_gemini',
            endpoint => 'gemini-3.5-flash-lite',
            model_params => JSON '{"generationConfig": {"temperature": 0}}',
            output_schema
            => "pull_forward_tier STRING OPTIONS(`enum`=['HIGH', 'MEDIUM', 'LOW']), reasoning STRING"
        ) AS assessment
    FROM
        scored s
        LEFT JOIN drivers d
            ON d.organization_code = s.organization_code
)
SELECT
    organization_code,
    hub_name,
    zone_id,
    zone_name,
    latitude,
    longitude,
    distance_km,
    market_radius_km,
    housing_units,
    owner_occupied_homes,
    critical_care_sites,
    food_retail_sites,
    hardware_retail_sites,
    critical_care_level,
    food_retail_level,
    hardware_retail_level,
    exposure_score,
    RANK() OVER (
        PARTITION BY organization_code ORDER BY exposure_score DESC
    ) AS exposure_rank,
    ROUND(
        SAFE_DIVIDE(
            exposure_score,
            SUM(exposure_score) OVER (PARTITION BY organization_code)
        ),
        4
    ) AS exposure_share,
    assessment.pull_forward_tier AS gemini_pull_forward_tier,
    assessment.reasoning AS gemini_reasoning,
    CURRENT_TIMESTAMP() AS refreshed_at
FROM
    assessed;
