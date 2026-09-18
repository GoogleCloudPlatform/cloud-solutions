# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
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
# # BigQuery 생성형 AI & 머신러닝 분석 (BigQuery ML & Vertex AI)
#
# 본 노트북은 BigQuery 외부의 데이터 이동 파이프라인 없이, **순수 SQL 쿼리만으로 LLM 인퍼런스, 텍스트 임베딩 생성 및 고속 벡터 검색(Vector Search)**을 대규모 데이터에 직접 적용하는 In-Database AI 파이프라인을 실습합니다.
#
# ### 학습 목표
# 1. **Vertex AI Remote Connection**: BigQuery 외부 연결(`vertex-connection`)을 통해 Gemini Flash 및 Text Embedding 모델을 선언합니다.
# 2. **`ML.GENERATE_TEXT`**: 이탈 위험 VIP 고객을 위한 초개인화 마케팅 추천 이메일을 실시간으로 자동 생성합니다.
# 3. **JSON Mode & SQL 정형 파싱**: LLM 응답을 일관된 JSON 형식으로 강제하고 SQL 함수로 안전하게 파싱하여 테이블에 적재합니다.
# 4. **`ML.GENERATE_EMBEDDING`**: 상품 카탈로그의 비정형 설명 텍스트를 768차원 밀집 벡터로 변환합니다.
# 5. **`VECTOR_SEARCH`**: 사용자 자연어 검색어와 상품 임베딩 간의 코사인 거리 기반 시맨틱 유사도 검색 엔진을 구현합니다.
#

# %% [markdown]
# ## Step 1: 환경 초기화 및 원격 모델 설정
#
# BigQuery에 저장된 데이터에서 직접 머신러닝 및 거대 생성 모델(Gemini)을 즉시 기동하기 위해, BigQuery 원격 연결(Remote Connection)을 수립하고 Vertex AI 서비스에 연결되는 Gemini 모델 리소스를 생성 및 등록합니다.

# %%
# [Qwiklabs 환경 대응] 만약 BigQuery API 호출 또는 매직 실행 중 HTTP Error 401 (Invalid authentication credentials) 에러가 발생한다면,
# 아래 줄의 주석을 해제하고 실행하여 1회성 수동 인증(ADC 생성)을 수행해 주세요.
# # !gcloud auth application-default login --no-launch-browser --quiet

import google.auth
from google.cloud import bigquery

# 활성 Google Cloud 프로젝트 ID 조회 및 클라이언트 구성
_, PROJECT_ID = google.auth.default()
bq_client = bigquery.Client(project=PROJECT_ID)

try:
    LOCATION = bq_client.get_dataset("thelook_ecommerce").location
except Exception:
    LOCATION = "us-central1"

print(f"Active Project ID: {PROJECT_ID}, Location: {LOCATION}")

# %%
# 1. Gemini Text 및 Embedding 모델 생성 (Python 클라이언트를 통해 동적 프로젝트 ID 바인딩)
create_models_query = f"""
-- 1. Gemini Text 모델 생성
CREATE OR REPLACE MODEL thelook_ecommerce.gemini_flash
REMOTE WITH CONNECTION `{PROJECT_ID}.{LOCATION}.vertex-connection`
OPTIONS(ENDPOINT = 'gemini-2.5-flash');

-- 2. Text Embedding 모델 생성
CREATE OR REPLACE MODEL thelook_ecommerce.text_embedding
REMOTE WITH CONNECTION `{PROJECT_ID}.{LOCATION}.vertex-connection`
OPTIONS(ENDPOINT = 'text-embedding-004');
"""

print("원격 모델 생성 쿼리 실행 중...")
query_job = bq_client.query(create_models_query)
query_job.result()  # 완료 대기
print("원격 모델(gemini_flash, text_embedding) 생성 완료!")

# %% [markdown]
# ## Step 2: 이탈 방지 개인화 추천 메일 생성 (`ML.GENERATE_TEXT`)
#
# 이탈 가능성이 높다고 판단된 고객군(예: 3개월간 구매가 없었으나 이전 구매 금액이 높은 VIP 고객) 중 일부를 선별하여, 그들이 마지막으로 구매했던 브랜드와 카테고리를 활용해 **개인화된 할인 쿠폰 마케팅 이메일**을 대량 생성합니다.
#
# BigQuery SQL 쿼리 내부에서 `ML.GENERATE_TEXT`와 Gemini 모델을 사용하여, 각 고객 맞춤 정보를 프롬프트로 동적 조립한 후 이메일 제목과 본문을 자동으로 추출해냅니다.

# %%
email_query = """
-- 이탈 위기 VIP 고객 대상 개인화 마케팅 메일 생성 (샘플 고객 선별)
WITH target_users AS (
  SELECT 
    u.id AS user_id,
    u.first_name,
    u.email,
    -- 최근 구매한 상품 정보
    p.brand AS last_bought_brand,
    p.category AS last_bought_category,
    p.name AS last_bought_product
  FROM thelook_ecommerce.users u
  JOIN thelook_ecommerce.order_items oi ON u.id = oi.user_id
  JOIN thelook_ecommerce.products p ON oi.product_id = p.id
  WHERE u.id IN (367, 100, 500, 1000) -- 고유 고객 샘플 선별
  QUALIFY ROW_NUMBER() OVER(PARTITION BY u.id ORDER BY oi.created_at DESC) = 1
),
prompts AS (
  SELECT
    user_id,
    first_name,
    email,
    CONCAT(
      "당신은 패션 쇼핑몰 'TheLook'의 친근한 마케팅 담당자입니다. 최근 구매 이력이 없는 고객을 다시 유치하기 위한 개인화된 할인 프로모션 이메일을 한국어로 작성해주세요. ",
      "고객 이름: ", first_name, ". ",
      "마지막으로 구매한 상품: 브랜드 '", last_bought_brand, "', 카테고리 '", last_bought_category, "', 상품명 '", last_bought_product, "'. ",
      "이 고객에게 동일한 브랜드 혹은 카테고리의 상품에 사용할 수 있는 20% 할인 쿠폰(코드: MISSYOU20)을 제안하며 구매를 유도하는 매력적인 메일을 써주세요. ",
      "제목은 반드시 '[TheLook]'으로 시작해야 하며, 본문은 정중하고 따뜻하며 간결한 어조로 작성해주세요. 이름이나 상품명 등에 플레이스홀더([Name] 등)를 남기지 말고 완성된 텍스트로 출력해주세요."
    ) AS prompt
  FROM target_users
)
SELECT 
  user_id,
  email,
  ml_generate_text_llm_result AS generated_email
FROM ML.GENERATE_TEXT(
  MODEL thelook_ecommerce.gemini_flash,
  (SELECT * FROM prompts),
  STRUCT(0.3 AS temperature, 1000 AS max_output_tokens, TRUE AS flatten_json_output)
);
"""

print("Gemini 모델을 호출하여 개인화 프로모션 메일을 생성 중입니다...")
email_df = bq_client.query(email_query).to_dataframe()
print(f"생성 완료된 개인화 이메일: 총 {len(email_df)}건\n")

for idx, row in email_df.iterrows():
    print("=" * 80)
    print(f"📧 수신자 #{idx + 1}: {row['email']} (고객 ID: {row['user_id']})")
    print("-" * 80)
    print(row["generated_email"].strip())
    print("=" * 80 + "\n")

# %% [markdown]
# ## Step 3: 다국어 번역 및 검색 키워드 태그 추출 (JSON Mode)
#
# TheLook 쇼핑몰의 상품 이름(`product_name`)은 영어로 등록되어 있습니다. 한국 고객층을 위한 **한국어 상품명 번역**을 일괄 수행하고, 자연어 검색 인덱스로 사용할 수 있도록 **상품 특징 키워드 태그(Tags)를 JSON 포맷으로 자동 추출**합니다.
#
# Gemini의 **JSON Mode**를 강제하여 출력 데이터의 형식을 정형화함으로써, 결과값을 BigQuery 내에서 파싱하여 바로 컬럼으로 가공할 수 있게 합니다.

# %%
# %%bigquery
-- 상품명 한국어 번역 및 검색 키워드 태그 추출 (Prompt-based JSON)
WITH target_products AS (
  SELECT 
    id AS product_id,
    name AS english_name,
    brand,
    category,
    retail_price
  FROM thelook_ecommerce.products
  WHERE id IN (19666, 18458, 21572, 22000) -- 일부 상품 선별
),
prompts AS (
  SELECT
    product_id,
    english_name,
    CONCAT(
      "제시된 상품 정보를 분석하여 상품명을 자연스러운 한국어로 번역하고, 상품의 스타일이나 소재를 나타내는 검색용 키워드 태그 3개를 추출해주세요. ",
      "영어 상품명: '", english_name, "', 브랜드: '", brand, "', 카테고리: '", category, "'. ",
      "출력은 반드시 'korean_name'(번역된 한국어 상품명 문자열)과 'tags'(키워드 태그 문자열 배열, 예: ['면', '캐주얼', '슬림핏']) 두 필드를 가진 하나의 JSON 객체여야 합니다. ",
      "마크다운 코드 블록 등의 형식을 사용하지 말고, 오직 순수한 JSON 문자열만 반환해주세요."
    ) AS prompt
  FROM target_products
)
SELECT 
  product_id,
  english_name,
  -- JSON 파싱하여 개별 컬럼으로 추출
  JSON_VALUE(ml_generate_text_llm_result, '$.korean_name') AS korean_name,
  JSON_QUERY(ml_generate_text_llm_result, '$.tags') AS search_tags,
  ml_generate_text_llm_result AS raw_json
FROM ML.GENERATE_TEXT(
  MODEL thelook_ecommerce.gemini_flash,
  (SELECT * FROM prompts),
  STRUCT(
    0.2 AS temperature,
    TRUE AS flatten_json_output
  )
);

# %% [markdown]
# ## Step 4: 상품 텍스트 임베딩 생성 (`ML.GENERATE_EMBEDDING`) 및 자연어 쿼리 기반 벡터 검색 (`VECTOR_SEARCH`)
#
# 이메일이나 키워드 검색 외에도, 고객이 입력한 자연어 쿼리("남자용 정장 바지", "comfy summer t-shirt")와 의미론적으로 가장 유사한 상품을 매칭하는 **벡터 검색(Vector Search)** 엔진을 구축합니다.
#
# 1.  `ML.GENERATE_EMBEDDING`을 활용하여 상품명과 브랜드, 카테고리를 합친 상품 설명 텍스트의 768차원 벡터 임베딩을 생성하여 테이블로 저장합니다.
# 2.  `VECTOR_SEARCH` 함수를 사용하여 임의의 검색 쿼리 벡터와 가장 코사인 유사도가 높은 상품 Top 5를 색인을 활용해 고속으로 조회합니다.

# %%
# %%bigquery
-- 1. 상품 카탈로그 임베딩 테이블 생성 (테스트용 100개 샘플링)
CREATE OR REPLACE TABLE thelook_ecommerce.product_embeddings AS
SELECT 
  id AS product_id,
  name AS product_name,
  brand,
  category,
  ml_generate_embedding_result AS product_embedding -- 768차원 벡터값 추출
FROM ML.GENERATE_EMBEDDING(
  MODEL thelook_ecommerce.text_embedding,
  (
    SELECT 
      id,
      name,
      brand,
      category,
      CONCAT("상품명: ", name, ", 브랜드: ", brand, ", 카테고리: ", category) AS content
    FROM thelook_ecommerce.products
    LIMIT 100
  ),
  STRUCT(TRUE AS flatten_json_output)
);

# %%
# %%bigquery
-- 2. 자연어 검색어 벡터를 사용한 상품 유사도 검색 (Vector Search)
WITH query_embedding AS (
  SELECT ml_generate_embedding_result AS q_embedding
  FROM ML.GENERATE_EMBEDDING(
    MODEL thelook_ecommerce.text_embedding,
    (SELECT '여름용 편안한 면 티셔츠' AS content),
    STRUCT(TRUE AS flatten_json_output)
  )
)
SELECT 
  base.product_id,
  base.product_name,
  base.brand,
  base.category,
  ROUND(distance, 4) AS cosine_distance
FROM VECTOR_SEARCH(
  TABLE thelook_ecommerce.product_embeddings,
  'product_embedding',
  TABLE query_embedding,
  'q_embedding',
  top_k => 5,
  distance_type => 'COSINE'
);
