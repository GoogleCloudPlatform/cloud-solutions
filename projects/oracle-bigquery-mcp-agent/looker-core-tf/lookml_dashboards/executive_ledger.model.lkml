connection: "default_bigquery_connection"

include: "/**/*.view"
include: "/**/*.dashboard"


explore: vw_executive_ledger {
  label: "Executive Enterprise Ledger Sync"
  description: "Real-time analytics view derived continuously from multi-tenant multicloud Oracle 19c database streaming operations."
}

explore: vw_spend_forecast {
  label: "180-Day Predictive ML Spend Forecast"
  description: "Predictive timeline models evaluated natively by BigQuery ML ARIMA_PLUS statistical sub-routines."
}
