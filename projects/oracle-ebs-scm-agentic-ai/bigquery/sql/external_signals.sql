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
-- VoltGuard demand and logistics signals
-- Dataset: `your-project-id.ebs_scm_agentic_ai`
-- Location: `your-bigquery-location` (the Google Trends public dataset is in
-- the US multi-region, and a query can't join datasets across locations)
--
--   * hub_market_areas: each hub's Nielsen designated market area (DMA) and
--     the coordinates that the Routes API and Weather API tools take.
--   * product_search_terms: search phrases that signal demand for each item.
--   * scenario_search_surge: the demo's South Florida surge, in the shape of
--     the Google Trends public dataset and labeled as a scenario signal.
--   * hub_search_signals: this week's top rising Google searches in every hub
--     market from bigquery-public-data.google_trends, plus the scenario.
--   * regional_search_trends_surge: the strongest matching search signal per
--     hub and item, as a demand multiplier of 1 + percent gain / 100.
--   * freight_lane_rates: contract truckload freight per transfer and lane.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS `your-project-id.ebs_scm_agentic_ai`
OPTIONS (
    location = 'your-bigquery-location',
    description = 'VoltGuard supply chain resiliency signals'
);

-- 1. Hub market areas: Google Trends DMA codes and hub coordinates.
CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.hub_market_areas` AS
SELECT *
FROM
    UNNEST([
        STRUCT(
            'MIA' AS organization_code,
            'Miami DC' AS hub_name,
            528 AS dma_id,
            'Miami-Ft. Lauderdale FL' AS dma_name,
            25.8195 AS latitude,
            -80.3553 AS longitude
        ),
        ('ATL', 'Atlanta Hub', 524, 'Atlanta GA', 33.7646, -84.5508),
        ('DAL', 'Dallas Hub', 623, 'Dallas-Ft. Worth TX', 32.7767, -96.7970),
        ('ORD', 'Chicago Hub', 602, 'Chicago IL', 41.9742, -87.9073),
        ('PHX', 'Phoenix Hub', 753, 'Phoenix AZ', 33.4484, -112.0740),
        ('EWR', 'Newark Hub', 501, 'New York NY', 40.6895, -74.1745)
    ]);

-- 2. Search phrases that signal demand for each item (RE2 patterns matched
--    against lowercase search terms).
CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.product_search_terms` AS
SELECT *
FROM
    UNNEST([
        STRUCT(
            'VG-GEN-7500' AS item_code,
            r'generator|power outage|brownout|blackout' AS search_term_pattern
        ),
        ('VG-SURGE-PRO', r'surge protector|power surge')
    ]);

-- 3. Scenario signal: the South Florida brownout surge that the demo replays,
--    with the same columns as bigquery-public-data.google_trends for the
--    current week. A 140% gain is a 2.4x demand multiplier.
CREATE OR REPLACE VIEW `your-project-id.ebs_scm_agentic_ai.scenario_search_surge` AS
SELECT
    CURRENT_DATE() AS refresh_date,
    DATE_TRUNC(CURRENT_DATE(), WEEK) AS week,
    s.dma_id,
    s.dma_name,
    s.term,
    s.rank,
    s.percent_gain,
    s.demand_driver
FROM
    UNNEST([
        STRUCT(
            528 AS dma_id,
            'Miami-Ft. Lauderdale FL' AS dma_name,
            'portable backup generator' AS term,
            1 AS rank,
            140 AS percent_gain,
            'Rolling grid brownouts across South Florida and a $500 municipal generator rebate' AS demand_driver
        ),
        (
            528,
            'Miami-Ft. Lauderdale FL',
            'whole home surge protector for brownouts',
            2,
            140,
            'Brownout voltage spikes drive whole-home surge protector searches alongside generators'
        ),
        (
            623,
            'Dallas-Ft. Worth TX',
            'portable backup generator',
            25,
            2,
            'Stable baseline grid conditions in North Texas'
        )
    ]) AS s;

-- 4. Rising searches in every hub market: the latest weekly top rising terms
--    from the Google Trends public dataset, plus the scenario signal. Public
--    refreshes can lag several days, so the view looks back 14 days for the
--    latest one.
CREATE OR REPLACE VIEW `your-project-id.ebs_scm_agentic_ai.hub_search_signals` AS
WITH recent_refreshes AS (
    SELECT
        refresh_date,
        week,
        dma_id,
        term,
        rank,
        percent_gain
    FROM
        `bigquery-public-data.google_trends.top_rising_terms`
    WHERE
        refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
),
latest_week AS (
    SELECT
        refresh_date,
        MAX(week) AS week
    FROM
        recent_refreshes
    WHERE
        refresh_date = (SELECT MAX(refresh_date) FROM recent_refreshes)
    GROUP BY
        refresh_date
),
signals AS (
    SELECT
        r.dma_id,
        r.term,
        r.week,
        r.rank,
        r.percent_gain,
        'Google Trends public dataset' AS signal_source,
        CAST(NULL AS STRING) AS demand_driver
    FROM
        recent_refreshes r
        INNER JOIN latest_week lw
            ON lw.refresh_date = r.refresh_date
            AND lw.week = r.week
    UNION ALL
    SELECT
        dma_id,
        term,
        week,
        rank,
        percent_gain,
        'Scenario signal' AS signal_source,
        demand_driver
    FROM
        `your-project-id.ebs_scm_agentic_ai.scenario_search_surge`
)
SELECT
    h.organization_code,
    h.hub_name,
    h.dma_name,
    s.term,
    s.week,
    s.rank,
    s.percent_gain,
    s.signal_source,
    s.demand_driver
FROM
    signals s
    INNER JOIN `your-project-id.ebs_scm_agentic_ai.hub_market_areas` h
        ON h.dma_id = s.dma_id;

-- 5. Demand multiplier per hub and item: the matching rising search with the
--    largest percent gain. Hub-items without a matching search have no row.
CREATE OR REPLACE VIEW `your-project-id.ebs_scm_agentic_ai.regional_search_trends_surge` AS
WITH matches AS (
    SELECT
        s.organization_code,
        s.hub_name,
        s.dma_name,
        p.item_code,
        ARRAY_AGG(
            STRUCT(
                s.term,
                s.week,
                s.percent_gain,
                s.signal_source,
                s.demand_driver
            )
            ORDER BY s.percent_gain DESC, s.rank
            LIMIT 1
        )[OFFSET(0)] AS top
    FROM
        `your-project-id.ebs_scm_agentic_ai.hub_search_signals` s
        INNER JOIN `your-project-id.ebs_scm_agentic_ai.product_search_terms` p
            ON REGEXP_CONTAINS(LOWER(s.term), p.search_term_pattern)
    -- A multiplier needs a numeric gain, so a term without one (a Google
    -- Trends Breakout) never sets it.
    WHERE
        s.percent_gain IS NOT NULL
    GROUP BY
        s.organization_code,
        s.hub_name,
        s.dma_name,
        p.item_code
)
SELECT
    organization_code,
    hub_name,
    dma_name,
    item_code,
    top.term AS top_rising_term,
    ROUND(1 + top.percent_gain / 100, 2) AS search_surge_multiplier,
    top.percent_gain AS search_percent_gain,
    top.signal_source,
    top.demand_driver AS demand_driver_summary,
    top.week AS signal_week
FROM
    matches;

-- 6. Contract truckload freight per transfer on each lane into Miami DC.
--    Live drive time and distance come from the Routes API tool.
CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.freight_lane_rates` AS
SELECT *
FROM
    UNNEST([
        STRUCT(
            'DAL' AS source_org_code,
            'Dallas Hub' AS source_hub_name,
            'MIA' AS dest_org_code,
            'Miami DC' AS dest_hub_name,
            1800.0 AS contract_freight_usd
        ),
        ('ATL', 'Atlanta Hub', 'MIA', 'Miami DC', 1120.0),
        ('ORD', 'Chicago Hub', 'MIA', 'Miami DC', 2100.0),
        ('PHX', 'Phoenix Hub', 'MIA', 'Miami DC', 3450.0),
        ('EWR', 'Newark Hub', 'MIA', 'Miami DC', 2050.0)
    ]);
