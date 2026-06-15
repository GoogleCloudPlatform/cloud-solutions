SELECT
  CAST(expense_date AS TIMESTAMP) AS expense_date,
  daily_spend AS actual_spend,
  NULL AS forecasted_spend
FROM (
  SELECT DATE(EXPENSE_DATE) AS expense_date, SUM(AMOUNT) AS daily_spend
  FROM `${project_id}.${dataset_id}.vw_executive_ledger`
  GROUP BY expense_date
)
UNION ALL
SELECT CAST(forecast_timestamp AS TIMESTAMP) AS expense_date, NULL AS actual_spend, forecast_value AS forecasted_spend
FROM ML.FORECAST(MODEL `${project_id}.${dataset_id}.spend_forecast_model`, STRUCT(180 AS horizon))
