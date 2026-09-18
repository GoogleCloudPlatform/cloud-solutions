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
# # BigQuery High-Level 선언형 AI Functions 실습
#
# 본 노트북은 별도의 머신러닝 모델 리소스를 생성하거나 복잡한 프롬프트 엔지니어링을 수행할 필요 없이, BigQuery에 내장된 고수준 **선언형 SQL AI 함수(High-Level AI Functions)**들을 사용하여 자연어 텍스트 처리, 시맨틱 검색 및 비용 최적화를 실습합니다.
#
# ### 학습 목표
# 1. **`AI.CLASSIFY`**: 비정형 상품명을 타겟 카테고리로 별도 모델 학습 없이 신속하게 자동 분류합니다.
# 2. **`AI.SIMILARITY`**: 두 문장 간의 의미론적 유사도(Semantic Similarity) 점수를 -1에서 1 사이의 실수로 산출합니다.
# 3. **`AI.IF`**: 데이터 레코드에 대해 자연어로 작성된 논리 조건(예: "겨울철 방한용 외투인가?")의 참/거짓(TRUE/FALSE)을 판정합니다.
# 4. **`AI.SEARCH` & 자율 임베딩(Autonomous Embedding)**: `STORED OPTIONS( asynchronous = TRUE )` 속성을 지정하여 데이터가 입력되면 백그라운드에서 임베딩이 자동 계산되는 자율 임베딩 컬럼을 구성하고 시맨틱 검색을 수행합니다.
# 5. **`AI.COUNT_TOKENS` & `optimization_mode`**: 토큰 수를 사전 측정하여 API 비용을 미터링하고, JIT(Just-In-Time) 지식 증류 최적화 모드로 대량 배치 연산 비용을 획기적으로 절감합니다.
#

# %% [markdown]
# ## Step 1: 환경 초기화
#
# 이 단계에서는 BigQuery Jupyter 매직 확장을 로드하고 실습 환경에서 원활한 High-Level AI Functions를 수행하기 위해 별도의 모델 정의나 Connection 등록 대신, 내부 기본 연결 채널을 확보합니다.

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

# %% [markdown]
# ## Step 2: 텍스트 분류 및 유사도 비교 (`AI.CLASSIFY` & `AI.SIMILARITY`)
#
# 별도의 프롬프트를 만들거나 모델 구조를 고민할 필요 없이, BigQuery에 내장된 함수를 통해 바로 분류 및 유사도 비교를 수행할 수 있습니다.
#
# ### 1. `AI.CLASSIFY`
# - **구문**: `ai.classify(text, categories)`
# - **용도**: 상품 정보, 고객 문의, 리뷰 등의 텍스트를 제공된 카테고리 후보 배열 중 가장 적합한 항목으로 매핑합니다.
#
# ### 2. `AI.SIMILARITY`
# - **구문**: `ai.similarity(text1, text2)`
# - **용도**: 두 문장 간의 의미상의 거리(유사도)를 `-1`에서 `1` 사이의 값(보통 `0`~`1`)으로 계산하여 줍니다. 키워드가 정확히 일치하지 않아도 의미적으로 유사한 표현("red shoes"와 "crimson footwear")을 매칭할 때 유용합니다.
#
# 아래 쿼리를 통해 실제로 작동 방식을 테스트해봅시다. 이 함수들은 BigQuery의 내부 기본 연결을 통해 Vertex AI 서비스를 호출하므로 원격 모델 생성 단계 없이 즉시 작동합니다.

# %%
# %%bigquery
-- 1. 상품명 텍스트 자동 대분류 분류 (AI.CLASSIFY)
WITH sample_products AS (
  SELECT id, name, category
  FROM thelook_ecommerce.products
  WHERE id IN (120, 5600, 15000, 20000)
)
SELECT 
  id AS product_id,
  name AS product_name,
  category AS original_category,
  -- 대분류 카테고리 지정하여 분류 수행
  ai.classify(name, ['Clothing', 'Footwear', 'Accessories', 'Electronics', 'Home']) AS predicted_category
FROM sample_products;

# %%
# %%bigquery
-- 2. 검색 쿼리와 상품 이름 간의 의미론적 유사도 계산 (AI.SIMILARITY)
WITH queries AS (
  SELECT 'warm winter coat' AS user_query, 'red leather shoes' AS target_concept
)
SELECT 
  user_query,
  -- 비슷한 의미를 지닌 다른 영문 설명과의 유사도 비교
  ai.similarity(user_query, 'Heavy wool jacket for cold weather') AS match_jacket_score,
  ai.similarity(user_query, 'Light cotton summer t-shirt') AS match_tshirt_score,
  
  target_concept,
  ai.similarity(target_concept, 'crimson leather footwear') AS match_shoes_score,
  ai.similarity(target_concept, 'blue denim pants') AS match_pants_score
FROM queries;

# %% [markdown]
# ## Step 3: 자연어 조건 판단 (`AI.IF`)
#
# `AI.IF` 함수는 주어진 텍스트가 자연어로 된 조건문(Condition)을 만족하는지 여부를 판단하여 **참(`True`)** 또는 **거짓(`False`)** 데이터를 리턴합니다.
#
# - **구문**: `ai.if(condition, text)`
# - **용도**: 텍스트 검열(욕설/스팸 필터링), 특정 의도 분석(환불 요청인지 문의인지 판별), 또는 의류 상품이 특정 계절용(예: 겨울용)인지 판별하는 등 다양한 시나리오에 응용 가능합니다.
#
# 아래 쿼리를 통해 특정 단어가 포함되어 있지 않아도 문맥상 '겨울 의류' 혹은 '부정적인 피드백'인지 판단하는 예시를 실습해봅니다.

# %%
# %%bigquery
-- 3. AI.IF를 통한 상품 문맥 정보 필터링 및 판단
WITH sample_data AS (
  SELECT 
    'Heavy goose down parka with fleece lining' AS description,
    '이 옷은 너무 얇아서 겨울에 입기 힘들 것 같아요. 배송도 일주일이나 걸렸습니다.' AS review
)
SELECT 
  -- 1) 상품이 겨울 방한용 의류에 해당하는지 여부 판단
  ai.if(('이 상품 설명이 따뜻한 겨울철 의류를 묘사하고 있나요? ', description)) AS is_winter_apparel,
  
  -- 2) 고객 리뷰가 불만이나 부정적인 감정을 지니고 있는지 판단
  ai.if(('이 고객 리뷰가 불만족이나 부정적인 피드백을 표현하고 있나요? ', review)) AS is_negative_review
FROM sample_data;

# %% [markdown]
# ## Step 4: 자율 임베딩 및 시맨틱 검색 (`AI.SEARCH`)
#
# 일반적인 벡터 검색(`VECTOR_SEARCH`)은 직접 임베딩 테이블을 구축하고 검색 쿼리 또한 실시간으로 임베딩 벡터로 변환하여 넘겨야 하는 번거로움이 있습니다.
#
# BigQuery의 **`AI.SEARCH`** 함수와 **자율 임베딩 생성(Autonomous Embedding Generation)** 기능을 함께 사용하면 이 과정이 매우 단순화됩니다.
#
# 1. **자율 임베딩 컬럼 선언**: 테이블 정의 시 특정 텍스트 컬럼이 변경되면 배후에서 임베딩 컬럼(`STRUCT<result ARRAY<FLOAT64>, status STRING>`)이 `AI.EMBED`를 통해 **비동기적으로 자동 생성 및 동기화**되도록 생성(`GENERATED ALWAYS AS`)합니다.
# 2. **`AI.SEARCH` 호출**: 인자값에 타겟 테이블, 원본 텍스트 컬럼명, 그리고 검색어를 전달하기만 하면 BigQuery가 검색어 임베딩 및 벡터 거리를 자동으로 처리해줍니다.
#
# 아래 쿼리를 통해 실제로 자율 임베딩 테이블을 빌드하고 검색하는 흐름을 확인해봅니다.

# %%
# 1. 자율 임베딩 테이블 생성 및 데이터 로드 (Python 클라이언트를 통해 동적 프로젝트 ID 바인딩)
create_auto_embed_query = f"""
-- 1. 자율 임베딩 컬럼을 포함하는 상품 카탈로그 테이블 생성
CREATE OR REPLACE TABLE thelook_ecommerce.products_auto_embed (
  product_id INT64,
  name STRING,
  description STRING,
  -- description 컬럼에 값이 들어오면 자동으로 text-embedding-005를 사용해 임베딩을 저장하는 컬럼 정의
  description_embedding STRUCT<result ARRAY<FLOAT64>, status STRING>
    GENERATED ALWAYS AS (AI.EMBED(
      description,
      connection_id => '{PROJECT_ID}.{LOCATION}.vertex-connection',
      endpoint => 'text-embedding-005'
    ))
    STORED OPTIONS( asynchronous = TRUE )
);

-- 2. 테스트용 상품 텍스트 데이터 로드 (인서트 이후 임베딩 연산이 백그라운드에서 자동으로 시작됩니다)
INSERT INTO thelook_ecommerce.products_auto_embed (product_id, name, description) VALUES
  (101, "Summer Linen Shirt", "Light and breathable short-sleeve shirt made of 100% linen, perfect for hot summer days."),
  (102, "Hiking Waterproof Windbreaker", "Windproof and waterproof functional jacket, ideal for hiking and outdoor activities in bad weather."),
  (103, "Business Casual Slacks", "Slim fit formal dress pants, clean and comfortable for office workers daily wear.");
"""

print("자율 임베딩 테이블 생성 및 샘플 데이터 로드 중...")
query_job = bq_client.query(create_auto_embed_query)
query_job.result()  # 완료 대기
print("자율 임베딩 테이블 및 샘플 데이터 로드 완료!")

# %% [markdown]
# > **[중요]**
# > 자율 임베딩 컬럼 옵션에 `asynchronous = TRUE`가 활성화되어 있어 데이터가 삽입된 후 몇 초 동안 백그라운드에서 임베딩 벡터가 비동기적으로 생성됩니다. 데이터 입력 후 약 5~10초 대기한 뒤 아래 검색 셀을 실행해 주세요.
#
# ### 3. `AI.SEARCH` 자연어 검색 실행
# 아래 쿼리는 `'야외 활동이나 산에 갈 때 입을 만한 아우터'`라는 완전한 자연어 검색어만을 전달하여 가장 관련성이 높은 상품을 자동으로 매칭합니다. `column_to_search` 인자값에는 임베딩 컬럼명이 아닌 **원본 소스 텍스트 컬럼인 `'description'`**을 입력하는 점에 주의하세요!

# %%
# %%bigquery
-- 3. AI.SEARCH를 사용한 자연어 기반 시맨틱 검색 실행
SELECT 
  base.product_id,
  base.name AS product_name,
  base.description,
  ROUND(distance, 4) AS distance
FROM AI.SEARCH(
  TABLE thelook_ecommerce.products_auto_embed,
  'description',                             -- 원본 텍스트 소스 컬럼명 지정
  
  # [테스트 케이스 선택] 원하는 자연어 검색어 한 줄만 주석 해제하고 실행해보세요.
  'comfortable jacket for hiking and outdoor activities', # 예시 1) Hiking Waterproof Windbreaker 매칭
  # 'clean formal pants for office wear', # 예시 2) Business Casual Slacks 매칭
  # 'cool short-sleeve shirt for hot summer days', # 예시 3) Summer Linen Shirt 매칭
  
  top_k => 2                                  -- 유사한 상위 2개 상품 매칭
);

# %% [markdown]
# ## Step 5: 비용 계량 및 최적화 (토큰 미터링 & 지식 증류)
#
# 대량의 데이터 분석 시 LLM API를 매 행마다 직접 호출하는 것은 매우 높은 지연 시간(Latency)과 비용을 유발합니다. BigQuery는 분석 실행 전에 사전에 비용을 산정하거나, 실행 시에 백엔드 성능을 크게 아끼기 위한 최적화 기법을 제공합니다.
#
# ### 1. `AI.COUNT_TOKENS`를 통한 토큰 계량
# 원격 LLM 모델에 프롬프트를 전송하기 전에 사전에 토큰 사용량과 예상 요금을 파악하는 기법입니다.
# - **구문**: `ai.count_tokens(text, endpoint => 'gemini-2.5-flash')`
#
# ### 2. `optimization_mode => 'MINIMIZE_COST'` (지식 증류 모드)
# `AI.IF`와 `AI.CLASSIFY`에서 대량의 행(최소 약 3,000행 이상 권장)을 평가할 때 사용할 수 있는 고성능 최적화 기법입니다.
# - **동작 방식**:
#   1. 전체 데이터 중 **아주 작은 샘플 데이터군**을 선별하여 원격 Gemini LLM을 직접 호출해 라벨링 데이터를 확보합니다.
#   2. 사전에 계산해둔 텍스트의 임베딩 데이터와 Gemini가 리턴한 라벨링 결과값을 학습용 피처로 삼아 **경량 증류 모델(Distilled Model)**을 실행 시점에 로컬에서 자동으로 훈련(JIT - Just In Time)합니다.
#   3. 로컬 경량 모델의 평가 정확도가 임계치를 통과하면, **나머지 수백만~수십억 개의 전체 데이터를 이 로컬 경량 모델을 사용해 고속으로 추론**합니다.
#   4. 이를 통해 직접 LLM API를 호출하는 횟수를 수백 분의 일로 절감하여 엄청난 비용 절감과 응답 지연 단축 혜택을 줍니다.
#
# 아래에서는 `AI.COUNT_TOKENS`를 사용한 비용 계산 시뮬레이션 및 `AI.IF` 최적화 모드 사용 방법의 쿼리 문법을 살펴봅니다.

# %%
# %%bigquery
-- 1. 마케팅 이메일 발송 전 프롬프트 토큰 개수 미터링 및 예상 비용 계산
WITH target_prompts AS (
  SELECT 
    u.id AS user_id,
    CONCAT(
      "당신은 패션 쇼핑몰 'TheLook'의 친근한 마케팅 담당자입니다. 최근 구매 이력이 없는 고객을 다시 유치하기 위한 개인화된 할인 프로모션 이메일을 한국어로 작성해주세요. ",
      "고객 이름: ", u.first_name, ". ",
      "마지막으로 구매한 상품: 브랜드 '", p.brand, "', 카테고리 '", p.category, "', 상품명 '", p.name, "'. ",
      "이 고객에게 동일한 브랜드 혹은 카테고리의 상품에 사용할 수 있는 20% 할인 쿠폰(코드: MISSYOU20)을 제안해주세요."
    ) AS prompt
  FROM thelook_ecommerce.users u
  JOIN thelook_ecommerce.order_items oi ON u.id = oi.user_id
  JOIN thelook_ecommerce.products p ON oi.product_id = p.id
  WHERE u.id IN (367, 100, 500, 1000) -- 샘플 고객 대상
  QUALIFY ROW_NUMBER() OVER(PARTITION BY u.id ORDER BY oi.created_at DESC) = 1
),
prompt_tokens AS (
  SELECT
    user_id,
    prompt,
    -- ai.count_tokens 호출하여 토큰 수 계산
    ai.count_tokens(prompt, endpoint => 'gemini-2.5-flash').result AS input_token_count
  FROM target_prompts
)
SELECT 
  user_id,
  input_token_count,
  -- 1 Million input token 당 $0.075로 비용 계산 시뮬레이션 (USD)
  ROUND((input_token_count / 1000000.0) * 0.075, 8) AS predicted_cost_usd,
  -- 환율 1,400원 기준 한화(KRW) 비용 계산 시뮬레이션
  ROUND((input_token_count / 1000000.0) * 0.075 * 1400.0, 4) AS predicted_cost_krw,
  prompt
FROM prompt_tokens;

# %%
# %%bigquery
-- 2. 대용량 데이터 대상 JIT(Just-in-Time) 지식 증류 최적화 모드 수행
-- 입력 3,100행(최소 기준 3,000행 초과)을 대상으로 경량 로컬 증류 모델을 자동 학습하여 LLM 호출 수와 비용을 수백 분의 일로 아끼며 추론합니다.
SELECT 
  name,
  category,
  AI.IF(
    ('이 상품이 의류(Clothing) 카테고리에 해당하나요? ', name),
    embeddings => AI.EMBED(name, endpoint => 'text-embedding-005').result,
    optimization_mode => 'MINIMIZE_COST'
  ) AS is_clothing
FROM thelook_ecommerce.products
LIMIT 3100;
