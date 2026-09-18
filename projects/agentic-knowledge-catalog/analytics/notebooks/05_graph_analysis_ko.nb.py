# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
# ---

# %%
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

# %% [markdown]
# # BigQuery Property Graph 생성, GQL 분석 및 대화형 시각화
#
# 본 노트북은 관계형 데이터베이스(RDB)에 저장된 `thelook_ecommerce` 테이블들을 **노드(Node)**와 **엣지(Edge)** 모델로 변환하여 **BigQuery Property Graph**를 구축하고, ISO 표준인 **GQL(Graph Query Language)**로 다중 홉(Multi-Hop) 네트워크 분석을 수행합니다.
#
# ### 학습 목표
# 1. **그래프 모델링**: 고객(Customer), 상품(Product), 거주지(Location), 물류센터(DistributionCenter) 노드 및 상호 연관 엣지 테이블을 설계합니다.
# 2. **BigQuery Property Graph 선언**: DDL 구문을 사용하여 정제된 노드/엣지 테이블을 하나의 통합 속성 그래프로 바인딩합니다.
# 3. **GQL 쿼리 및 네이티브 시각화**: `%%bigquery --graph display_only` 매직을 통해 노트북 내에서 직접 대화형 Force Layout 그래프를 렌더링하고 탐색합니다.
# 4. **콘솔 UI 검증**: BigQuery Studio 콘솔의 Graphs 탭에서 시각적 스키마 정의를 검토합니다.
#

# %% [markdown]
# ## Step 1: 초기 환경 설정
#
# BigQuery 클라이언트 라이브러리를 임포트하고 인증 정보를 로드하여 실습을 위한 초기 환경을 설정합니다.

# %%
# [Qwiklabs 환경 대응] 만약 BigQuery 매직(%%bigquery) 실행 중 HTTP Error 401 (Invalid authentication credentials) 에러가 발생한다면,
# 아래 줄의 주석을 해제하고 실행하여 1회성 수동 인증(ADC 생성)을 수행해 주세요.
# # !gcloud auth application-default login --no-launch-browser --quiet

# 필요 라이브러리 및 확장 로드
# %load_ext google.cloud.bigquery

import google.auth
from google.auth.transport.requests import Request
from google.cloud import bigquery

# 기본 설정
credentials, PROJECT_ID = google.auth.default()
bq_client = bigquery.Client(project=PROJECT_ID)
try:
    LOCATION = bq_client.get_dataset("thelook_ecommerce").location
except Exception:
    LOCATION = "us-central1"
credentials.refresh(Request())

print(f"Google Cloud Project ID: {PROJECT_ID}")

# %% [markdown]
# ## Step 2: 속성 그래프(Property Graph)용 노드 및 엣지 테이블 구축
#
# 정제 레이어용 데이터셋(`thelook_network`)을 생성하고, 그래프를 구성할 노드(Customer, Product, Location, DC) 및 엣지(ordered, co_purchased, lives_in, supplied_from) 테이블을 생성합니다.

# %%
from google.api_core.exceptions import Conflict

client = bigquery.Client()

# 0. 정제 레이어용 데이터셋 생성 (존재하지 않을 경우)
dataset_id = f"{PROJECT_ID}.thelook_network"
dataset = bigquery.Dataset(dataset_id)
dataset.location = LOCATION

try:
    client.create_dataset(dataset, timeout=30)
    print(f"데이터셋 '{dataset_id}'이 생성되었습니다.")
except Conflict:
    print(f"데이터셋 '{dataset_id}'이 이미 존재합니다.")

# 1. 노드 및 엣지 테이블 생성 SQL
setup_tables_sql = f"""
-- 1) 노드 테이블 생성
CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_users` AS
SELECT id AS user_id, age, gender, traffic_source
FROM `{PROJECT_ID}.thelook_ecommerce.users`;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_products` AS
SELECT id AS product_id, category, brand, name AS product_name, retail_price
FROM `{PROJECT_ID}.thelook_ecommerce.products`;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_locations` AS
SELECT 
  ROW_NUMBER() OVER (ORDER BY country, city) AS location_id,
  city, country
FROM (
  SELECT DISTINCT city, country 
  FROM `{PROJECT_ID}.thelook_ecommerce.users`
  WHERE city IS NOT NULL AND country IS NOT NULL
);

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.node_distribution_centers` AS
SELECT id AS center_id, name AS center_name
FROM `{PROJECT_ID}.thelook_ecommerce.distribution_centers`;

-- 2) 엣지 테이블 생성 (각 테이블별 고유 ID 컬럼 필수 포함)
CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_ordered` AS
SELECT 
  id AS order_item_id, user_id, product_id, sale_price, status
FROM `{PROJECT_ID}.thelook_ecommerce.order_items`;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_lives_in` AS
SELECT 
  CONCAT(u.id, '_lives_in_', l.location_id) AS edge_id,
  u.id AS user_id,
  l.location_id
FROM `{PROJECT_ID}.thelook_ecommerce.users` u
JOIN `{PROJECT_ID}.thelook_network.node_locations` l
  ON u.city = l.city AND u.country = l.country;

CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_supplied_from` AS
SELECT 
  CONCAT(id, '_supplied_from_', distribution_center_id) AS edge_id,
  id AS product_id,
  distribution_center_id AS center_id
FROM `{PROJECT_ID}.thelook_ecommerce.products`;

-- 동시구매 엣지 생성
CREATE OR REPLACE TABLE `{PROJECT_ID}.thelook_network.edge_co_purchased` AS
WITH product_pairs AS (
  SELECT 
    a.product_id AS source_product_id,
    b.product_id AS target_product_id,
    COUNT(*) AS co_purchase_count
  FROM `{PROJECT_ID}.thelook_ecommerce.order_items` a
  JOIN `{PROJECT_ID}.thelook_ecommerce.order_items` b 
    ON a.order_id = b.order_id AND a.product_id < b.product_id
  GROUP BY 1, 2
)
SELECT 
  CONCAT(source_product_id, '_', target_product_id, '_copurchase') AS edge_id,
  source_product_id,
  target_product_id,
  co_purchase_count
FROM product_pairs
WHERE co_purchase_count >= 2;
"""

print("노드 및 엣지 테이블을 생성 중입니다...")
client.query(setup_tables_sql).result()
print("모든 노드 및 엣지 테이블이 성공적으로 생성되었습니다.")

# %% [markdown]
# ## Step 3: BigQuery Property Graph 생성
#
# 생성된 노드 및 엣지 테이블들의 관계(Source/Destination Key 매핑)를 정의하여 속성 그래프 `product_recommendation_graph`를 등록합니다.

# %%
create_graph_sql = f"""
CREATE OR REPLACE PROPERTY GRAPH `{PROJECT_ID}.thelook_network.product_recommendation_graph`
NODE TABLES (
  `{PROJECT_ID}.thelook_network.node_products` AS Product KEY (product_id)
    PROPERTIES (product_id, category, brand, product_name, retail_price),
  `{PROJECT_ID}.thelook_network.node_users` AS Customer KEY (user_id)
    PROPERTIES (user_id, age, gender, traffic_source),
  `{PROJECT_ID}.thelook_network.node_locations` AS Location KEY (location_id)
    PROPERTIES (city, country),
  `{PROJECT_ID}.thelook_network.node_distribution_centers` AS DistributionCenter KEY (center_id)
    PROPERTIES (center_id, center_name)
)
EDGE TABLES (
  `{PROJECT_ID}.thelook_network.edge_ordered` AS ordered
    KEY (order_item_id)
    SOURCE KEY (user_id) REFERENCES Customer (user_id)
    DESTINATION KEY (product_id) REFERENCES Product (product_id)
    PROPERTIES (order_item_id, sale_price, status),
  `{PROJECT_ID}.thelook_network.edge_co_purchased` AS co_purchased_with
    KEY (edge_id)
    SOURCE KEY (source_product_id) REFERENCES Product (product_id)
    DESTINATION KEY (target_product_id) REFERENCES Product (product_id)
    PROPERTIES (co_purchase_count),
  `{PROJECT_ID}.thelook_network.edge_lives_in` AS lives_in
    KEY (edge_id)
    SOURCE KEY (user_id) REFERENCES Customer (user_id)
    DESTINATION KEY (location_id) REFERENCES Location (location_id),
  `{PROJECT_ID}.thelook_network.edge_supplied_from` AS supplied_from
    KEY (edge_id)
    SOURCE KEY (product_id) REFERENCES Product (product_id)
    DESTINATION KEY (center_id) REFERENCES DistributionCenter (center_id)
)
"""

print("속성 그래프를 생성 중입니다...")
client.query(create_graph_sql).result()
print("속성 그래프(product_recommendation_graph)가 성공적으로 등록되었습니다.")

# %% [markdown]
# ## Step 4: 특정 상품 주문 고객 네트워크 분석 및 네이티브 시각화
#
# 특정 인기 상품(`product_id = 25346`)을 중심으로 **[공급 물류센터 ➡️ 상품 ➡️ 구매한 여러 고객들 ➡️ 고객들의 거주 지역]**으로 확장되는 다차원 관계를 분석합니다.
#
# Colab Enterprise의 네이티브 그래프 시각화 기능(`--graph display_only`)을 사용하여 1개의 상품 노드를 중심으로 여러 고객들이 별 모양(Star)으로 연결되는 시각적 네트워크를 인라인으로 확인합니다.
#
# > [!NOTE]
# >
# > **BigQuery Graph 및 에디션 요구사항**: 네이티브 GQL 쿼리(`GRAPH_TABLE(...)`)
# > 실행은 BigQuery **Enterprise** 또는 **Enterprise Plus** 에디션 예약
# > 할당(`SET @@reservation = '...';`)이 필수적입니다.
# > Qwiklabs와 같은 온디맨드(On-Demand) 컴퓨팅 환경에서는 아래의 표준 SQL
# > 다중 테이블 `JOIN` 쿼리가 BigQuery Studio 네이티브 GQL JSON 규격(`kind`,
# > `identifier`, `labels`, `properties`, `source_node_identifier`, `destination_node_identifier`)에
# > 맞추어 노드와 엣지를 생성하여, 에디션 예약 없이도 Colab Enterprise 네이티브
# > 인터랙티브 그래프 시각화를 정상적으로 렌더링할 수 있도록 지원합니다.

# %%
# %%bigquery --graph display_only
SELECT
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('customer_', CAST(u.user_id AS STRING)) AS identifier,
    ['Customer'] AS labels,
    STRUCT(
      u.user_id AS user_id,
      u.age AS age,
      u.gender AS gender,
      u.traffic_source AS traffic_source
    ) AS properties
  )) AS Customer_Node,
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('product_', CAST(p.product_id AS STRING)) AS identifier,
    ['Product'] AS labels,
    STRUCT(
      p.product_id AS product_id,
      p.category AS category,
      p.brand AS brand,
      p.product_name AS product_name,
      p.retail_price AS retail_price
    ) AS properties
  )) AS Product_Node,
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('dc_', CAST(dc.center_id AS STRING)) AS identifier,
    ['DistributionCenter'] AS labels,
    STRUCT(
      dc.center_id AS center_id,
      dc.center_name AS center_name
    ) AS properties
  )) AS DC_Node,
  TO_JSON(STRUCT(
    'node' AS kind,
    CONCAT('location_', CAST(l.location_id AS STRING)) AS identifier,
    ['Location'] AS labels,
    STRUCT(
      l.location_id AS location_id,
      l.city AS city,
      l.country AS country
    ) AS properties
  )) AS Location_Node,
  TO_JSON(STRUCT(
    'edge' AS kind,
    CONCAT('ordered_', CAST(o.order_item_id AS STRING)) AS identifier,
    ['ordered'] AS labels,
    CONCAT('customer_', CAST(u.user_id AS STRING)) AS source_node_identifier,
    CONCAT('product_', CAST(p.product_id AS STRING)) AS destination_node_identifier,
    STRUCT(
      o.order_item_id AS order_item_id,
      o.sale_price AS sale_price,
      o.status AS status
    ) AS properties
  )) AS Ordered_Edge,
  TO_JSON(STRUCT(
    'edge' AS kind,
    CONCAT('supplied_from_', CAST(sf.edge_id AS STRING)) AS identifier,
    ['supplied_from'] AS labels,
    CONCAT('product_', CAST(p.product_id AS STRING)) AS source_node_identifier,
    CONCAT('dc_', CAST(dc.center_id AS STRING)) AS destination_node_identifier,
    STRUCT(
      sf.edge_id AS edge_id
    ) AS properties
  )) AS Supplied_Edge,
  TO_JSON(STRUCT(
    'edge' AS kind,
    CONCAT('lives_in_', CAST(lives.edge_id AS STRING)) AS identifier,
    ['lives_in'] AS labels,
    CONCAT('customer_', CAST(u.user_id AS STRING)) AS source_node_identifier,
    CONCAT('location_', CAST(l.location_id AS STRING)) AS destination_node_identifier,
    STRUCT(
      lives.edge_id AS edge_id
    ) AS properties
  )) AS Lives_In_Edge
FROM thelook_network.node_products p
JOIN thelook_network.edge_supplied_from sf ON p.product_id = sf.product_id
JOIN thelook_network.node_distribution_centers dc ON sf.center_id = dc.center_id
JOIN thelook_network.edge_ordered o ON p.product_id = o.product_id
JOIN thelook_network.node_users u ON o.user_id = u.user_id
JOIN thelook_network.edge_lives_in lives ON u.user_id = lives.user_id
JOIN thelook_network.node_locations l ON lives.location_id = l.location_id
WHERE p.product_id = 25346
LIMIT 100;

# %% [markdown]
# ### 최신 GQL 패턴 매칭 쿼리 레퍼런스 (Enterprise Edition 전용)
#
# 활성 예약이 할당된 BigQuery Enterprise 또는 Enterprise Plus 에디션에서는 위의 7개 테이블 관계형 `JOIN`을 직관적인 ISO 표준 GQL 패턴 매칭 문법으로 간결하게 작성할 수 있습니다:
#
# ```sql
# SELECT
#   TO_JSON(c) AS Customer_Node,
#   TO_JSON(p) AS Product_Node,
#   TO_JSON(o) AS Ordered_Edge,
#   TO_JSON(dc) AS DC_Node,
#   TO_JSON(sf) AS Supplied_Edge,
#   TO_JSON(l) AS Location_Node,
#   TO_JSON(lives) AS Lives_In_Edge
# FROM GRAPH_TABLE(
#   thelook_network.product_recommendation_graph
#   MATCH (dc:DistributionCenter)<-[sf:supplied_from]-(p:Product)<-[o:ordered]-(c:Customer)-[lives:lives_in]->(l:Location)
#   WHERE p.product_id = 25346
#   RETURN c, p, o, dc, sf, l, lives
# )
# LIMIT 100;
# ```
#
# `MATCH (dc)<-[:supplied_from]-(p)<-[:ordered]-(c)-[:lives_in]->(l)`와 같이 다단계 노드/엣지 경로를 단일 직관적 패턴으로 표현할 수 있습니다.

# %% [markdown]
# ## Step 5: BigQuery UI 콘솔 속성 그래프 검증 및 GQL 장점
#
# ### 1. BigQuery Studio 콘솔 UI에서 그래프 스키마 확인
# BigQuery Studio 탐색기에서 `thelook_network` 데이터셋을 열고 **`Graphs`** 탭을 선택한 후 `product_recommendation_graph`를 클릭합니다:
# - **4 Nodes**: `Customer`, `Product`, `DistributionCenter`, `Location`
# - **4 Edges**: `co_purchased_with`(동시구매), `lives_in`(거주), `ordered`(주문), `supplied_from`(공급)
# - 노드와 엣지의 매핑 구조가 그래픽 다이어그램으로 완벽하게 표현됩니다.
#
# ### 2. 속성 그래프와 GQL의 실무적 장점
# - **복잡한 JOIN 제거**: 관계형 데이터베이스에서 여러 테이블을 다중 조인(Multi-Join)하는 대신, 간결한 경로 패턴 매칭(`MATCH (c:Customer)-[:ordered]->(p:Product)`) 문법으로 쿼리를 직관화합니다.
# - **다중 홉(Multi-Hop) 분석**: "A 상품을 구매한 고객이 함께 구매한 B 상품을 구매한 다른 고객들의 거주지 분포"와 같은 복잡한 네트워크 연관 관계를 고속으로 추출할 수 있습니다.
# - **실무 응용 분야**: 이상 금융거래 탐지(Fraud Detection), 연관 상품 추천 엔진(Recommendation System), 소셜 네트워크 분석 등 고급 분석 파이프라인에 핵심 기술로 활용됩니다.
#
