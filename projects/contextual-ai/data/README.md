# Ecommerce IT Operations Demo Data

This directory contains realistic ecommerce IT operations data designed to
demonstrate correlations between system health and business metrics.

## Data Overview

### 📊 Tables Generated

-   **revenue_metrics** (721 records)

    -   `timestamp`, `hourly_revenue`, `transaction_count`, `avg_order_value`
    -   Hourly revenue data with realistic business patterns

-   **system_performance** (721 records)

    -   `timestamp`, `avg_response_time_ms`, `error_rate_percent`,
      `requests_per_second`
    -   System-level performance metrics

-   **user_activity** (721 records)

    -   `timestamp`, `active_users`, `page_views`, `bounce_rate_percent`,
      `conversion_rate_percent`
    -   User behavior and engagement metrics

-   **infrastructure_health** (2,884 records)

    -   `timestamp`, `service_name`, `cpu_percent`, `memory_percent`,
      `api_response_time_ms`
    -   Per-service infrastructure metrics for 4 microservices

## 📈 Business Patterns Built In

### Daily Patterns

-   **Low overnight** (10 PM -   6 AM): 30% of baseline traffic
-   **Morning ramp-up** (7-10 AM): Gradual increase
-   **Lunch peak** (11 AM -   1 PM): 120% of baseline
-   **Afternoon dip** (2-4 PM): 90% of baseline
-   **Evening peak** (5-8 PM): 140% of baseline
-   **Late evening** (9-10 PM): 80% of baseline

### Weekly Patterns

-   **Weekdays**: Normal baseline traffic
-   **Saturday**: 130% of weekday traffic
-   **Sunday**: 80% of weekday traffic

## 🚨 Incident Scenarios

### 1. Payment Gateway Outage

**When**: Day 7, 2:00-5:00 PM (3 hours) **Impact**:

-   Revenue drops 85% (payment failures)
-   Error rate spikes 25x normal
-   Response time increases 4.5x
-   Bounce rate increases 2.5x
-   Conversion rate drops 90%
-   Payment API CPU/memory stress

### 2. System-Wide Slowdown

**When**: Day 15, 7:00-9:00 PM (2 hours) **Impact**:

-   Revenue drops 40% (frustrated users)
-   Response time increases 2.8x
-   Error rate increases 8x
-   Bounce rate increases 80%
-   Conversion rate drops 50%
-   All services show elevated resource usage

### 3. Flash Sale Event

**When**: Day 21, 10:00 AM -   2:00 PM (4 hours) **Impact**:

-   Revenue spikes 350% (successful sale)
-   Traffic increases 420%
-   Response time increases 80% (under load)
-   Error rate triples (but manageable)
-   Bounce rate decreases 30% (motivated buyers)
-   Conversion rate increases 80%
-   All infrastructure under stress

## 🔧 Services Monitored

-   **web-frontend**: Main application frontend
-   **payment-api**: Payment processing service
-   **inventory-service**: Product inventory management
-   **recommendation-engine**: Product recommendations

Each service has realistic resource usage patterns and responds differently to
incidents.

## 🚀 Quick Start

### Generate Data

```bash
cd data
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy
python generate_ecommerce_data.py
```

### Import to BigQuery

```bash
# Install BigQuery dependency
pip install google-cloud-bigquery

# Update PROJECT_ID in import_to_bigquery.py
# Then run:
python import_to_bigquery.py
```

### View Generated Files

-   `revenue_metrics.csv`
-   `system_performance.csv`
-   `user_activity.csv`
-   `infrastructure_health.csv`

## 📋 Analysis Ideas

### Key Questions the Data Can Answer

-   **"Why did revenue drop at 3 PM on [Day 7]?"**

    -   Payment gateway outage correlation
    -   Error rates and response times spiked
    -   User behavior changed (high bounce rate)

-   **"Which service caused the slowdown on [Day 15]?"**

    -   All services showed stress
    -   Payment API particularly impacted
    -   Cascade effect across the system

-   **"How did our infrastructure handle the flash sale?"**

    -   Revenue success despite performance degradation
    -   Recommendation engine was bottleneck
    -   Users more tolerant during sales

-   **"What's the normal correlation between response time and revenue?"**

    -   When response time >2000ms, revenue drops significantly
    -   1% error rate threshold for business impact
    -   User patience varies by time of day

### Sample Queries

```sql
--   Revenue impact during incidents
SELECT
  timestamp,
  hourly_revenue,
  avg_response_time_ms,
  error_rate_percent
FROM revenue_metrics r
JOIN system_performance s ON r.timestamp = s.timestamp
WHERE avg_response_time_ms > 2000
ORDER BY timestamp;

--   Service performance during flash sale
SELECT
  timestamp,
  service_name,
  cpu_percent,
  memory_percent,
  api_response_time_ms
FROM infrastructure_health
WHERE timestamp BETWEEN '2024-05-XX 10:00:00' AND '2024-05-XX 14:00:00'
  AND service_name = 'recommendation-engine'
ORDER BY timestamp;

--   User behavior correlation with system health
SELECT
  u.timestamp,
  active_users,
  bounce_rate_percent,
  conversion_rate_percent,
  avg_response_time_ms
FROM user_activity u
JOIN system_performance s ON u.timestamp = s.timestamp
WHERE bounce_rate_percent > 60
ORDER BY timestamp;
```

## 🎯 Perfect for Testing

This dataset is ideal for:

-   **AI/ML model training** on IT operations data
-   **Dashboard development** with realistic patterns
-   **Alerting system testing** with clear anomalies
-   **Root cause analysis** practice
-   **Business impact correlation** demonstrations

The data tells a clear story with obvious "smoking guns" that AI systems should
be able to identify and explain to operations teams.
