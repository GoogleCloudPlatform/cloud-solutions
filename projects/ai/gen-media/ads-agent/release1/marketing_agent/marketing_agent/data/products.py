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

# pylint: disable=C0114, W1405

from google.cloud import bigquery
from marketing_agent.config import BQ_DATASET, PROJECT_ID
from marketing_agent.schema import (
    Attributes,
    Categorization,
    CommercialStatus,
    CoreIdentifiers,
    Description,
    Media,
    Product,
)

_CACHED_PRODUCTS: list[Product] | None = None


def _row_to_product(row) -> Product:
    return Product(
        core_identifiers=CoreIdentifiers(
            sku=row.sku,
            product_name=row.name,
            brand=row.brand or "",
        ),
        attributes=Attributes(
            color_name=getattr(row, 'color_name', None),
            material=getattr(row, 'material', None),
        ),
        categorization=Categorization(
            department=row.department,
            category=row.category,
        ),
        commercial_status=CommercialStatus(
            cost_price=row.cost,
            current_price=row.retail_price,
            msrp=row.msrp,
            in_stock=True,
        ),
        media=Media(main_image_url=row.image_uri),
        description=Description(
            short=row.short_description,
            long=row.long_description,
        ),
    )


def retrieve_products() -> list[Product]:
    """Returns all products from BigQuery. Caches after first read."""
    global _CACHED_PRODUCTS
    if _CACHED_PRODUCTS is not None:
        return _CACHED_PRODUCTS

    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT sku, name, brand, department, category,
               color_name, material, cost, retail_price, msrp,
               short_description, long_description, image_uri
        FROM `{BQ_DATASET}.products`
    """
    _CACHED_PRODUCTS = [_row_to_product(row) for row in client.query(query)]
    return _CACHED_PRODUCTS


def get_product_by_sku_from_bq(sku: str) -> Product | None:
    """Fetches a single product by SKU from BigQuery."""
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT sku, name, brand, department, category,
               color_name, material, cost, retail_price, msrp,
               short_description, long_description, image_uri
        FROM `{BQ_DATASET}.products`
        WHERE sku = @sku
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("sku", "STRING", sku)]
    )
    rows = list(client.query(query, job_config=job_config))
    if rows:
        return _row_to_product(rows[0])
    return None
