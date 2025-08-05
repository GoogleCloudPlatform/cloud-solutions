# Ecommerce Operations API Documentation

This document describes the new ecommerce operations endpoints added to the
Contextual AI API.

## Endpoints Overview

### 📊 Revenue Metrics

#### GET `/revenue`

Get paginated revenue metrics including hourly revenue, transaction count, and
average order value.

**Parameters:**

- `page` (int, default=1): Page number (1-indexed)
- `page_size` (int, default=20, max=100): Records per page
- `start_date` (string, optional): Start date (YYYY-MM-DD format)
- `end_date` (string, optional): End date (YYYY-MM-DD format)
- `min_revenue` (float, optional): Minimum hourly revenue filter

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/revenue?page=1&page_size=5"
```

**Response:**

```json
{
  "page": 1,
  "page_size": 5,
  "total_records": 721,
  "total_pages": 145,
  "data": [
    {
      "timestamp": "2025-06-11T17:00:00",
      "hourly_revenue": 60902.5,
      "transaction_count": 691,
      "avg_order_value": 88.05
    }
  ]
}
```

#### GET `/revenue/trends`

Get revenue trends with daily/hourly aggregations.

**Parameters:**

- `aggregation` (string, default="daily"): "hourly" or "daily"
- `days` (int, default=7, max=30): Number of days to analyze

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/revenue/trends?aggregation=daily&days=7"
```

### ⚡ System Performance

#### GET `/performance`

Get system performance metrics including response times, error rates, and
requests per second.

**Parameters:**

- `page` (int, default=1): Page number
- `page_size` (int, default=20, max=100): Records per page
- `min_response_time` (float, optional): Minimum response time filter (ms)
- `min_error_rate` (float, optional): Minimum error rate filter (%)

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/performance?min_response_time=1000"
```

### 👥 User Activity

#### GET `/users`

Get user activity metrics including active users, page views, bounce rate, and
conversion rate.

**Parameters:**

- `page` (int, default=1): Page number
- `page_size` (int, default=20, max=100): Records per page
- `min_users` (int, optional): Minimum active users filter

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/users?page=1&page_size=10"
```

### 🏗️ Infrastructure Health

#### GET `/infrastructure`

Get infrastructure health metrics for all services.

**Parameters:**

- `page` (int, default=1): Page number
- `page_size` (int, default=50, max=200): Records per page
- `service_name` (string, optional): Filter by service name
- `min_cpu` (float, optional): Minimum CPU usage filter (%)
- `min_memory` (float, optional): Minimum memory usage filter (%)

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/infrastructure?service_name=payment-api&min_cpu=90"
```

#### GET `/infrastructure/services`

Get list of all monitored services.

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/infrastructure/services"
```

**Response:**

```json
{
  "services": [
    "inventory-service",
    "payment-api",
    "recommendation-engine",
    "web-frontend"
  ]
}
```

### 🚨 Incident Detection

#### GET `/incidents`

Automatically detect incident periods based on performance and business metrics.

**Parameters:**

- `response_time_threshold` (float, default=1500): Response time threshold (ms)
- `error_rate_threshold` (float, default=5.0): Error rate threshold (%)
- `revenue_drop_threshold` (float, default=30.0): Revenue drop threshold (%)

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/incidents?response_time_threshold=1000&error_rate_threshold=3"
```

**Response:**

```json
{
  "incident_count": 2,
  "incidents": [
    {
      "start_time": "2025-05-20T07:00:00",
      "end_time": "2025-05-20T10:00:00",
      "duration_hours": 4.0,
      "incident_type": "High Error Rate",
      "severity": "critical",
      "revenue_impact": 125000.50,
      "avg_response_time_ms": 1500.2,
      "avg_error_rate_percent": 15.5,
      "description": "High Error Rate incident lasting 4.0 hours with critical severity"
    }
  ],
  "total_revenue_impact": 250000.75,
  "thresholds_used": {
    "response_time_ms": 1000,
    "error_rate_percent": 3,
    "revenue_drop_percent": 30
  }
}
```

### 📈 Analysis & Correlations

#### GET `/correlation`

Analyze correlations between system performance and business metrics.

**Parameters:**

- `start_date` (string, optional): Start date for analysis (YYYY-MM-DD)
- `end_date` (string, optional): End date for analysis (YYYY-MM-DD)

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/correlation"
```

#### GET `/dashboard`

Get summary data for operations dashboard.

**Example:**

```bash
curl "https://contextual-ai-apis-ieejvgvenq-uc.a.run.app/ecommerce_ops/dashboard"
```

**Response:**

```json
{
  "latest_metrics": {
    "timestamp": "2025-06-11T17:00:00",
    "hourly_revenue": 60902.5,
    "transaction_count": 691,
    "avg_response_time_ms": 216.3,
    "error_rate_percent": 0.37,
    "active_users": 4127,
    "conversion_rate_percent": 2.13
  },
  "service_health": [
    {
      "service_name": "payment-api",
      "avg_cpu": 45.2,
      "avg_memory": 62.1,
      "avg_response_time": 350.5
    }
  ],
  "daily_trends": [
    {
      "hour": 17,
      "avg_revenue": 58000.0,
      "avg_response_time": 280.5
    }
  ],
  "status": "operational"
}
```

## Data Model

### Services Monitored

- **web-frontend**: Main application frontend
- **payment-api**: Payment processing service
- **inventory-service**: Product inventory management
- **recommendation-engine**: Product recommendations

### Metric Types

- **Revenue Metrics**: Business performance indicators
- **System Performance**: Technical performance metrics
- **User Activity**: User behavior and engagement
- **Infrastructure Health**: Service-level resource utilization

### Incident Severity Levels

- **critical**: Response time ≥ 3000ms OR error rate ≥ 10%
- **high**: Response time ≥ 1500ms OR error rate ≥ 5%
- **medium**: Moderate performance degradation

## Use Cases

### 1. Operations Dashboard

```bash
# Get current status
curl "/ecommerce_ops/dashboard"

# Get recent incidents
curl "/ecommerce_ops/incidents?response_time_threshold=1000"

# Get service health
curl "/ecommerce_ops/infrastructure?page_size=20"
```

### 2. Performance Investigation

```bash
# Find performance issues
curl "/ecommerce_ops/performance?min_response_time=1000"

# Check infrastructure during issues
curl "/ecommerce_ops/infrastructure?service_name=payment-api&min_cpu=80"

# Analyze business impact
curl "/ecommerce_ops/correlation?start_date=2025-05-20&end_date=2025-05-21"
```

### 3. Business Analysis

```bash
# Revenue trends
curl "/ecommerce_ops/revenue/trends?aggregation=daily&days=7"

# User behavior patterns
curl "/ecommerce_ops/users?page_size=24"

# High revenue periods
curl "/ecommerce_ops/revenue?min_revenue=80000"
```

## Integration Notes

- All endpoints support CORS for frontend integration
- Timestamps are in ISO 8601 format (UTC)
- Pagination follows consistent pattern across endpoints
- Error responses include detailed error messages
- All endpoints are unauthenticated for demo purposes

## FastAPI Documentation

Interactive API documentation is available at:
`https://<Your endpoint url>/docs`

This provides a complete interface for testing all endpoints with example
requests and responses.
