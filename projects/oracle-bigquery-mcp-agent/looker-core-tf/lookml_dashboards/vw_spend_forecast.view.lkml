view: vw_spend_forecast {
  sql_table_name: `oracle_ledger_sync.vw_spend_forecast` ;;

  dimension_group: expense_date {
    type: time
    timeframes: [raw, date, week, month]
    sql: ${TABLE}.expense_date ;;
  }

  measure: actual_spend {
    type: sum
    value_format_name: usd
    sql: ${TABLE}.actual_spend ;;
  }

  measure: forecasted_spend {
    type: sum
    value_format_name: usd
    sql: ${TABLE}.forecasted_spend ;;
  }
}
