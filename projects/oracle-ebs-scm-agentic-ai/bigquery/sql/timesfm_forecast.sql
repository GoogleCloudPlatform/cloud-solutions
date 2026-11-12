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
-- BigQuery ML TimesFM (`AI.FORECAST`) demand sensing tables and views
-- Dataset: `your-project-id.ebs_scm_agentic_ai`
-- =============================================================================

-- 1. Daily issue history that TimesFM forecasts from. The demo scenario posts
--    no issue transactions in Oracle EBS, so the view seeds 90 days of daily
--    issues per hub and item, ending yesterday: each hub-item's mean demand
--    with a day-to-day variation of up to 30%. The variation depends on the
--    number of days before today, not on the date, so TimesFM gets the same
--    series and returns the same forecast every day. To forecast real demand,
--    aggregate the Oracle EBS issue transactions here instead.
CREATE OR REPLACE VIEW `your-project-id.ebs_scm_agentic_ai.hub_daily_issue_history` AS
WITH hub_items AS (
    SELECT *
    FROM
        UNNEST([
            STRUCT(
                'MIA' AS organization_code,
                'VG-GEN-7500' AS item_code,
                21.4 AS mean_daily_qty
            ),
            ('ATL', 'VG-GEN-7500', 2.0),
            ('DAL', 'VG-GEN-7500', 9.5),
            ('ORD', 'VG-GEN-7500', 2.0),
            ('PHX', 'VG-GEN-7500', 6.0),
            ('EWR', 'VG-GEN-7500', 1.2),
            ('MIA', 'VG-SURGE-PRO', 6.0),
            ('ATL', 'VG-SURGE-PRO', 2.0),
            ('DAL', 'VG-SURGE-PRO', 1.5),
            ('ORD', 'VG-SURGE-PRO', 2.0),
            ('PHX', 'VG-SURGE-PRO', 1.2),
            ('EWR', 'VG-SURGE-PRO', 1.5)
        ])
)
SELECT
    h.organization_code,
    h.item_code,
    issue_date,
    ROUND(
        h.mean_daily_qty * (
            0.7 + 0.6 * MOD(
                ABS(FARM_FINGERPRINT(
                    CONCAT(
                        h.organization_code,
                        h.item_code,
                        CAST(DATE_DIFF(CURRENT_DATE(), issue_date, DAY) AS STRING)
                    )
                )),
                1001
            ) / 1000
        )
    ) AS daily_issued_qty
FROM
    hub_items h,
    UNNEST(
        GENERATE_DATE_ARRAY(
            DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY),
            DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
        )
    ) AS issue_date;

-- 2. TimesFM zero-shot forecast (`AI.FORECAST`) of daily demand for the next
--    14 days per hub and item, with a 95% prediction interval. The deployment
--    stores each forecast with its date and generation time, so planner
--    questions read a table instead of waiting for TimesFM. A BigQuery
--    scheduled query reruns this file every day, so the stored forecast
--    follows the issue history.
CREATE OR REPLACE TABLE `your-project-id.ebs_scm_agentic_ai.timesfm_hub_baseline_forecast` AS
SELECT
    organization_code,
    item_code,
    DATE(forecast_timestamp) AS forecast_date,
    forecast_value,
    prediction_interval_lower_bound,
    prediction_interval_upper_bound,
    CURRENT_TIMESTAMP() AS generated_at
FROM
    AI.FORECAST(
        TABLE `your-project-id.ebs_scm_agentic_ai.hub_daily_issue_history`,
        data_col => 'daily_issued_qty',
        timestamp_col => 'issue_date',
        id_cols => ['organization_code', 'item_code'],
        horizon => 14,
        confidence_level => 0.95
    );

-- 3. The forecast that the agent reads: the stored forecast from today on.
--    Days before today drop out, so a missed refresh shortens the horizon
--    instead of moving old forecasts onto today. A matching rising search
--    multiplies the baseline. Without one, surged demand equals the baseline.
CREATE OR REPLACE VIEW `your-project-id.ebs_scm_agentic_ai.timesfm_hub_burn_forecast` AS
SELECT
    f.organization_code,
    f.item_code,
    f.forecast_date,
    ROUND(f.forecast_value, 2) AS baseline_daily_burn_qty,
    ROUND(f.prediction_interval_lower_bound, 2) AS lower_bound_qty,
    ROUND(f.prediction_interval_upper_bound, 2) AS upper_bound_qty,
    s.search_surge_multiplier,
    CASE
        WHEN s.item_code IS NULL THEN ROUND(f.forecast_value, 2)
        ELSE ROUND(f.forecast_value * s.search_surge_multiplier, 2)
    END AS surged_daily_burn_qty,
    s.top_rising_term,
    s.signal_source,
    s.demand_driver_summary,
    f.generated_at AS forecast_generated_at
FROM
    `your-project-id.ebs_scm_agentic_ai.timesfm_hub_baseline_forecast` f
    LEFT JOIN `your-project-id.ebs_scm_agentic_ai.regional_search_trends_surge` s
        ON s.organization_code = f.organization_code
        AND s.item_code = f.item_code
WHERE
    f.forecast_date >= CURRENT_DATE();
