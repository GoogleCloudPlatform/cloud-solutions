CREATE OR REPLACE MODEL `${project_id}.${dataset_id}.spend_forecast_model`
OPTIONS(model_type="ARIMA_PLUS", time_series_timestamp_col="expense_date", time_series_data_col="daily_spend", data_frequency="DAILY") AS
SELECT DATE(EXPENSE_DATE) AS expense_date, SUM(AMOUNT) AS daily_spend
FROM `${project_id}.${dataset_id}.vw_executive_ledger`
GROUP BY expense_date
