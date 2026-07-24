# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.cloud import bigquery
from ..config import PROJECT_ID, BQ_DATASET
from ..schema import (
    Product,
    CoreIdentifiers,
    Attributes,
    Categorization,
    CommercialStatus,
    Media,
    Description,
)


class SalesTool:
    def __init__(self):
        self.client = bigquery.Client(project=PROJECT_ID)

    def find_low_velocity(self) -> list[Product]:
        """Identifies items with low sales velocity — actual sales significantly below forecast."""
        query = f"""
            SELECT
                p.sku, p.name, p.brand, p.department, p.category,
                p.cost, p.retail_price, p.short_description, p.long_description, p.image_uri,
                i.stock_level, i.sales_velocity,
                i.actual_sales, i.forecasted_sales
            FROM `{BQ_DATASET}.inventory_analysis` AS i
            JOIN `{BQ_DATASET}.products` AS p ON i.sku = p.sku
            WHERE i.actual_sales < (i.forecasted_sales * 0.6)
            ORDER BY i.stock_level DESC
            LIMIT 15
        """

        try:
            results = []
            for row in self.client.query(query):
                pct = (
                    round(row.actual_sales / row.forecasted_sales * 100, 1)
                    if row.forecasted_sales
                    else 0
                )
                results.append(
                    Product(
                        core_identifiers=CoreIdentifiers(
                            sku=row.sku, product_name=row.name, brand=row.brand or ""
                        ),
                        attributes=Attributes(),
                        categorization=Categorization(
                            department=row.department,
                            category=row.category,
                        ),
                        commercial_status=CommercialStatus(
                            cost_price=row.cost,
                            current_price=row.retail_price,
                            stock_quantity=row.stock_level,
                            in_stock=True,
                            sales_velocity=row.sales_velocity or "Low",
                            sales_reasoning=f"Sales at {pct}% of forecast ({row.actual_sales} vs {row.forecasted_sales})",
                        ),
                        media=Media(main_image_url=row.image_uri),
                        description=Description(
                            short=row.short_description,
                            long=row.long_description,
                        ),
                    )
                )
            return results
        except Exception as e:
            print(f"BigQuery Error in SalesTool: {e}")
            return []
