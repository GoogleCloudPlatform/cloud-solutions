#!/usr/bin/env python3

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Generate realistic ecommerce IT operations demo data for BigQuery.
Creates story-driven data with clear incidents and
business impact correlations.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducible data
np.random.seed(42)
random.seed(42)


def create_timestamps():
    """Create hourly timestamps for the last 30 days"""
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=30)

    timestamps = []
    current = start_time
    while current <= end_time:
        timestamps.append(current)
        current += timedelta(hours=1)

    return timestamps


def get_hour_multiplier(timestamp):
    """Get traffic multiplier based on hour of day"""
    hour = timestamp.hour
    # Business hours pattern: low overnight, peaks at lunch and evening
    if 22 <= hour or hour <= 6:  # Night
        return 0.3
    elif 7 <= hour <= 10:  # Morning ramp up
        return 0.7 + (hour - 7) * 0.1
    elif 11 <= hour <= 13:  # Lunch peak
        return 1.2
    elif 14 <= hour <= 16:  # Afternoon
        return 0.9
    elif 17 <= hour <= 20:  # Evening peak
        return 1.4
    else:  # Late evening
        return 0.8


def get_day_multiplier(timestamp):
    """Get traffic multiplier based on day of week"""
    weekday = timestamp.weekday()
    # 0=Monday, 6=Sunday
    if weekday < 5:  # Weekdays
        return 1.0
    elif weekday == 5:  # Saturday
        return 1.3
    else:  # Sunday
        return 0.8


def is_incident_time(timestamp, incident_periods):
    """Check if timestamp falls within an incident period"""
    for start, end in incident_periods:
        if start <= timestamp <= end:
            return True
    return False


def generate_revenue_metrics(timestamps):
    """Generate revenue metrics with realistic patterns and anomalies"""
    print("Generating revenue_metrics...")

    # Define incident periods
    base_time = timestamps[0]

    revenue_data = []
    base_hourly_revenue = 50000  # $50k base hourly revenue

    for timestamp in timestamps:
        # Apply time-based multipliers
        hour_mult = get_hour_multiplier(timestamp)
        day_mult = get_day_multiplier(timestamp)

        # Base revenue calculation
        revenue = base_hourly_revenue * hour_mult * day_mult

        # Add some randomness
        revenue *= 0.8 + random.random() * 0.4  # ±20% variance

        # Handle special events
        if (
            base_time + timedelta(days=7, hours=14)
            <= timestamp
            <= base_time + timedelta(days=7, hours=17)
        ):
            # Payment gateway outage - severe drop
            revenue *= 0.15
        elif (
            base_time + timedelta(days=15, hours=19)
            <= timestamp
            <= base_time + timedelta(days=15, hours=21)
        ):
            # System slowdown - moderate drop
            revenue *= 0.6
        elif (
            base_time + timedelta(days=21, hours=10)
            <= timestamp
            <= base_time + timedelta(days=21, hours=14)
        ):
            # Flash sale - major spike
            revenue *= 3.5

        # Calculate transaction metrics
        avg_order_value = 85 + random.gauss(0, 15)  # ~$85 AOV with variance
        transaction_count = int(revenue / avg_order_value)

        revenue_data.append(
            {
                "timestamp": timestamp,
                "hourly_revenue": round(revenue, 2),
                "transaction_count": transaction_count,
                "avg_order_value": round(avg_order_value, 2),
            }
        )

    return pd.DataFrame(revenue_data)


def generate_system_performance(timestamps):
    """Generate system performance metrics with incident correlations"""
    print("Generating system_performance...")

    performance_data = []

    for timestamp in timestamps:
        # Base response time (200-800ms normal)
        base_response_time = 300 + random.gauss(0, 150)

        # Normal error rate (<1%)
        base_error_rate = 0.2 + random.random() * 0.6

        # Base RPS
        hour_mult = get_hour_multiplier(timestamp)
        day_mult = get_day_multiplier(timestamp)
        base_rps = 150 * hour_mult * day_mult * (0.8 + random.random() * 0.4)

        # Apply incident effects
        base_time = timestamps[0]

        if (
            base_time + timedelta(days=7, hours=14)
            <= timestamp
            <= base_time + timedelta(days=7, hours=17)
        ):
            # Payment gateway outage
            base_response_time *= 4.5  # Severe slowdown
            base_error_rate *= 25  # High error rate
            base_rps *= 0.3  # Reduced traffic
        elif (
            base_time + timedelta(days=15, hours=19)
            <= timestamp
            <= base_time + timedelta(days=15, hours=21)
        ):
            # System slowdown
            base_response_time *= 2.8
            base_error_rate *= 8
            base_rps *= 0.7
        elif (
            base_time + timedelta(days=21, hours=10)
            <= timestamp
            <= base_time + timedelta(days=21, hours=14)
        ):
            # Flash sale - high load
            base_response_time *= 1.8
            base_error_rate *= 3
            base_rps *= 4.5

        performance_data.append(
            {
                "timestamp": timestamp,
                "avg_response_time_ms": max(50, round(base_response_time, 1)),
                "error_rate_percent": min(50, round(base_error_rate, 2)),
                "requests_per_second": max(10, round(base_rps, 1)),
            }
        )

    return pd.DataFrame(performance_data)


def generate_user_activity(timestamps):
    """Generate user activity metrics showing business impact"""
    print("Generating user_activity...")

    activity_data = []

    for timestamp in timestamps:
        # Base metrics
        hour_mult = get_hour_multiplier(timestamp)
        day_mult = get_day_multiplier(timestamp)

        # Active users
        base_users = 2500 * hour_mult * day_mult * (0.8 + random.random() * 0.4)

        # Page views (typically 3-5 per user)
        page_views = base_users * (3 + random.random() * 2)

        # Normal bounce rate (30-50%)
        bounce_rate = 35 + random.gauss(0, 8)

        # Normal conversion rate (2-4%)
        conversion_rate = 2.8 + random.gauss(0, 0.6)

        # Apply incident effects
        base_time = timestamps[0]

        if (
            base_time + timedelta(days=7, hours=14)
            <= timestamp
            <= base_time + timedelta(days=7, hours=17)
        ):
            # Payment gateway outage
            bounce_rate *= 2.5  # Users leave due to payment issues
            conversion_rate *= 0.1  # Can't complete purchases
            base_users *= 0.7  # Word spreads, users avoid site
        elif (
            base_time + timedelta(days=15, hours=19)
            <= timestamp
            <= base_time + timedelta(days=15, hours=21)
        ):
            # System slowdown
            bounce_rate *= 1.8
            conversion_rate *= 0.5
            base_users *= 0.8
        elif (
            base_time + timedelta(days=21, hours=10)
            <= timestamp
            <= base_time + timedelta(days=21, hours=14)
        ):
            # Flash sale
            base_users *= 4.2  # Traffic surge
            bounce_rate *= 0.7  # Lower bounce (motivated buyers)
            conversion_rate *= 1.8  # Higher conversion (sale prices)
            page_views = base_users * 6  # More browsing during sale

        activity_data.append(
            {
                "timestamp": timestamp,
                "active_users": max(100, int(base_users)),
                "page_views": max(300, int(page_views)),
                "bounce_rate_percent": max(10, min(90, round(bounce_rate, 1))),
                "conversion_rate_percent": max(
                    0.1, min(15, round(conversion_rate, 2))
                ),
            }
        )

    return pd.DataFrame(activity_data)


def generate_infrastructure_health(timestamps):
    """Generate infrastructure health metrics with service-level detail"""
    print("Generating infrastructure_health...")

    services = [
        "web-frontend",
        "payment-api",
        "inventory-service",
        "recommendation-engine",
    ]
    infrastructure_data = []

    for timestamp in timestamps:
        hour_mult = get_hour_multiplier(timestamp)
        day_mult = get_day_multiplier(timestamp)
        load_factor = hour_mult * day_mult

        for service in services:
            # Service-specific base metrics
            if service == "web-frontend":
                base_cpu = 30 + load_factor * 25
                base_memory = 45 + load_factor * 20
                base_api_time = 200 + random.gauss(0, 50)
            elif service == "payment-api":
                base_cpu = 25 + load_factor * 30
                base_memory = 40 + load_factor * 25
                base_api_time = 300 + random.gauss(0, 80)
            elif service == "inventory-service":
                base_cpu = 35 + load_factor * 20
                base_memory = 50 + load_factor * 15
                base_api_time = 150 + random.gauss(0, 40)
            else:  # recommendation-engine
                base_cpu = 45 + load_factor * 35
                base_memory = 55 + load_factor * 25
                base_api_time = 400 + random.gauss(0, 100)

            # Add randomness
            base_cpu += random.gauss(0, 5)
            base_memory += random.gauss(0, 5)

            # Apply incident effects
            base_time = timestamps[0]

            if (
                base_time + timedelta(days=7, hours=14)
                <= timestamp
                <= base_time + timedelta(days=7, hours=17)
            ):
                # Payment gateway outage
                if service == "payment-api":
                    base_cpu *= 2.5
                    base_memory *= 1.8
                    base_api_time *= 6
                elif service == "web-frontend":
                    base_cpu *= 1.6  # Handling retries
                    base_api_time *= 2
            elif (
                base_time + timedelta(days=15, hours=19)
                <= timestamp
                <= base_time + timedelta(days=15, hours=21)
            ):
                # System-wide slowdown
                base_cpu *= 1.7
                base_memory *= 1.4
                base_api_time *= 2.5
            elif (
                base_time + timedelta(days=21, hours=10)
                <= timestamp
                <= base_time + timedelta(days=21, hours=14)
            ):
                # Flash sale - all services under load
                base_cpu *= 2.2
                base_memory *= 1.6
                base_api_time *= 1.9
                if service == "recommendation-engine":
                    base_cpu *= 1.5  # Extra load from recommendations

            infrastructure_data.append(
                {
                    "timestamp": timestamp,
                    "service_name": service,
                    "cpu_percent": max(5, min(95, round(base_cpu, 1))),
                    "memory_percent": max(10, min(90, round(base_memory, 1))),
                    "api_response_time_ms": max(50, round(base_api_time, 1)),
                }
            )

    return pd.DataFrame(infrastructure_data)


def main():
    """Generate all demo data files"""
    print("Generating ecommerce IT operations demo data...")
    print("Time range: Last 30 days, hourly granularity")
    print()

    # Create timestamps
    timestamps = create_timestamps()
    print(f"Generated {len(timestamps)} hourly timestamps")

    # Generate all datasets
    revenue_df = generate_revenue_metrics(timestamps)
    performance_df = generate_system_performance(timestamps)
    activity_df = generate_user_activity(timestamps)
    infrastructure_df = generate_infrastructure_health(timestamps)

    # Save to CSV files
    print("\nSaving data files...")
    revenue_df.to_csv("revenue_metrics.csv", index=False)
    performance_df.to_csv("system_performance.csv", index=False)
    activity_df.to_csv("user_activity.csv", index=False)
    infrastructure_df.to_csv("infrastructure_health.csv", index=False)

    print("\n✅ Demo data generation complete!")
    print("\nKey Story Elements Generated:")
    print(
        (
            "📉 Payment Gateway Outage (Day 7, 2-5 PM): "
            "Revenue drops 85%, errors spike"
        )
    )
    print(
        (
            "🐌 System Slowdown (Day 15, 7-9 PM): "
            "Response time 3x slower, conversions drop"
        )
    )
    print(
        (
            "🚀 Flash Sale Event (Day 21, 10 AM-2 PM): "
            "Revenue 3.5x spike, infrastructure stress"
        )
    )
    print("\nFiles created:")
    print("- revenue_metrics.csv")
    print("- system_performance.csv")
    print("- user_activity.csv")
    print("- infrastructure_health.csv")

    # Print sample data insights
    print("\nData Summary:")
    print(f"Revenue metrics: {len(revenue_df)} records")
    print(f"System performance: {len(performance_df)} records")
    print(f"User activity: {len(activity_df)} records")
    print(f"Infrastructure health: {len(infrastructure_df)} records")


if __name__ == "__main__":
    main()
