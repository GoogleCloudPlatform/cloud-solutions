- dashboard: fynanceai_enterprise_financial_operations
  title: "FynanceAI: Enterprise Financial Operations & 180-Day Predictive Intelligence"
  layout: newspaper
  preferred_viewer: dashboards-next
  description: "High-fidelity cloud dashboard streaming transactional ledger logs straight from multitenant Oracle instances, driving executive KPI summaries and automated predictive forecasting models."

  elements:
    # 1. KPI Summary Tile: Total Tracked Operational Spend
    - name: total_operational_spend
      title: "Total Tracked Operational Spend"
      type: single_value
      model: executive_ledger
      explore: vw_executive_ledger
      measures: [vw_executive_ledger.total_spend]
      listen: {}
      row: 0
      col: 0
      width: 8
      height: 4

    # 2. KPI Summary Tile: Transactions Pending Review
    - name: pending_review_count
      title: "Transactions Pending Forensic Review"
      type: single_value
      model: executive_ledger
      explore: vw_executive_ledger
      measures: [vw_executive_ledger.pending_approval_count]
      listen: {}
      row: 0
      col: 8
      width: 8
      height: 4

    # 3. KPI Summary Tile: Overall Transaction Volume
    - name: overall_transaction_volume
      title: "Overall Transaction Volume"
      type: single_value
      model: executive_ledger
      explore: vw_executive_ledger
      measures: [vw_executive_ledger.total_transaction_count]
      listen: {}
      row: 0
      col: 16
      width: 8
      height: 4

    # 4. Bar Chart: Regional Budget Allocation vs Tracked Realized Costs
    - name: regional_budget_variance
      title: "Regional Budget Allocation vs Tracked Realized Costs"
      type: looker_column
      model: executive_ledger
      explore: vw_executive_ledger
      dimensions: [vw_executive_ledger.region_name]
      measures: [vw_executive_ledger.total_spend, vw_executive_ledger.allocated_budget]
      sorts: [vw_executive_ledger.total_spend desc]
      limit: 500
      x_axis_gridlines: false
      y_axis_gridlines: true
      show_view_names: false
      show_y_axis_labels: true
      show_y_axis_ticks: true
      y_axis_tick_density: default
      y_axis_tick_density_custom: 5
      show_x_axis_label: true
      show_x_axis_ticks: true
      y_axis_scale_mode: linear
      x_axis_reversed: false
      y_axis_reversed: false
      plot_size_by_field: false
      trellis: ''
      stacking: ''
      limit_displayed_rows: false
      legend_position: center
      point_style: none
      show_value_labels: true
      label_density: 25
      x_axis_scale: auto
      y_axis_combined: true
      ordering: none
      show_null_labels: false
      show_totals_labels: false
      show_silhouette: false
      totals_color: "#808080"
      row: 4
      col: 0
      width: 12
      height: 8

    # 5. Don't Chart: Spend Distribution Breakdown by Target Operations Department
    - name: department_spend_distribution
      title: "Spend Distribution Breakdown by Target Operations Department"
      type: looker_pie
      model: executive_ledger
      explore: vw_executive_ledger
      dimensions: [vw_executive_ledger.department_name]
      measures: [vw_executive_ledger.total_spend]
      sorts: [vw_executive_ledger.total_spend desc]
      limit: 500
      value_labels: legend
      label_type: labPer
      inner_radius: 50
      row: 4
      col: 12
      width: 12
      height: 8

    # 6. Line Chart: 180-Day Machine Learning Spend Forecast Timeline
    - name: predictive_spend_timeline
      title: "180-Day Machine Learning Predictive Spend Timeline (ARIMA_PLUS)"
      type: looker_line
      model: executive_ledger
      explore: vw_spend_forecast
      dimensions: [vw_spend_forecast.expense_date_date]
      measures: [vw_spend_forecast.actual_spend, vw_spend_forecast.forecasted_spend]
      sorts: [vw_spend_forecast.expense_date_date desc]
      limit: 1000
      x_axis_gridlines: false
      y_axis_gridlines: true
      show_view_names: false
      show_y_axis_labels: true
      show_y_axis_ticks: true
      y_axis_tick_density: default
      y_axis_tick_density_custom: 5
      show_x_axis_label: true
      show_x_axis_ticks: true
      y_axis_scale_mode: linear
      x_axis_reversed: false
      y_axis_reversed: false
      plot_size_by_field: false
      trellis: ''
      stacking: ''
      limit_displayed_rows: false
      legend_position: center
      point_style: circle
      show_value_labels: false
      label_density: 25
      x_axis_scale: auto
      y_axis_combined: true
      show_null_points: false
      interpolation: linear
      series_colors:
        vw_spend_forecast.actual_spend: "#1A73E8"
        vw_spend_forecast.forecasted_spend: "#E53935"
      row: 12
      col: 0
      width: 24
      height: 10

    # 7. Map Chart: Global Transaction Distribution Heat Map
    - name: global_transaction_heat_map
      title: "Global Transaction Heat Map"
      type: looker_geo_choropleth
      model: executive_ledger
      explore: vw_executive_ledger
      dimensions: [vw_executive_ledger.country_name]
      measures: [vw_executive_ledger.total_transaction_count]
      colors: ["#8ab4f8", "#4285f4", "#1a73e8", "#174ea6", "#0d2c6c", "#05163f"]
      show_view_names: false
      show_legend: true
      quantize_colors: false
      map_plot_mode: points
      map_tile_provider: light
      map_position: fit_data
      row: 22
      col: 0
      width: 24
      height: 10
