view: vw_executive_ledger {
  sql_table_name: `oracle_ledger_sync.vw_executive_ledger` ;;

  dimension: expense_id {
    primary_key: yes
    type: number
    sql: ${TABLE}.EXPENSE_ID ;;
  }

  dimension: amount {
    type: number
    sql: ${TABLE}.AMOUNT ;;
  }

  dimension_group: expense_date {
    type: time
    timeframes: [raw, time, date, week, month, quarter, year]
    sql: ${TABLE}.EXPENSE_DATE ;;
  }

  dimension: merchant_name {
    type: string
    sql: ${TABLE}.MERCHANT_NAME ;;
  }

  dimension: status {
    type: string
    sql: ${TABLE}.STATUS ;;
  }

  dimension: employee_name {
    type: string
    sql: ${TABLE}.employee_name ;;
  }

  dimension: department_name {
    type: string
    sql: ${TABLE}.DEPT_NAME ;;
  }

  dimension: category_name {
    type: string
    sql: ${TABLE}.CATEGORY_NAME ;;
  }

  dimension: allocated_budget {
    type: number
    sql: ${TABLE}.ALLOCATED_BUDGET ;;
  }

  dimension: country_name {
    type: string
    map_layer_name: countries
    sql: ${TABLE}.COUNTRY_NAME ;;
  }

  dimension: region_name {
    type: string
    sql: ${TABLE}.REGION_NAME ;;
  }

  measure: total_spend {
    type: sum
    value_format_name: usd
    sql: ${amount} ;;
  }

  measure: average_spend {
    type: average
    value_format_name: usd
    sql: ${amount} ;;
  }

  measure: pending_approval_count {
    type: count
    filters: [status: "PENDING"]
  }

  measure: total_transaction_count {
    type: count
  }
}
