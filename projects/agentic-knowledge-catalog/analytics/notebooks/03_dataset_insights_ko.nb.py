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
# # Dataset Insights: 데이터셋 레벨 종합 요약 및 테이블 관계 분석
#
# 본 노트북은 개별 테이블 단위를 넘어 데이터셋(`thelook_ecommerce`) 전체에 존재하는 다수의 테이블 관계를 종합적으로 이해하고, 비즈니스 레벨의 종합 요약 및 외래키 연관 관계를 도출하는 파이프라인을 구축합니다.
#
# ### 학습 목표
# 1. **데이터셋 레벨 인사이트**: 단일 테이블을 넘어 전체 이커머스 비즈니스 관점의 종합 설명을 생성합니다.
# 2. **관계 네트워크 추출(Entity Relationships)**: LLM 분석을 통해 테이블 간의 논리적/물리적 연관 관계(Relationship)를 자동으로 추론합니다.
# 3. **거버넌스 연동**: 데이터셋 카탈로그에 설명과 관계 메타데이터를 동기화하여 대화형 에이전트의 기반 자원으로 활용합니다.
#
# ---
#
# ### [실행 전 콘솔 UI 확인]
# 노트북을 실행하기 전, BigQuery Studio 탐색기에서 `thelook_ecommerce` 데이터셋을 클릭하고 **Insights** 탭을 열어보세요:
# - "Insights have not yet been generated" 문구와 함께 아직 데이터셋 수준의 인사이트가 없는 상태입니다.
#

# %% [markdown]
# ## Step 1: 환경 초기화

# %%
# [Qwiklabs 환경 대응] 만약 Dataplex API 호출 중 HTTP Error 401 (Invalid authentication credentials) 에러가 발생한다면,
# 아래 줄의 주석을 해제하고 실행하여 1회성 수동 인증(ADC 생성)을 수행해 주세요.
# # !gcloud auth application-default login --no-launch-browser --quiet

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from google.cloud import bigquery

# 1. Google Cloud 프로젝트 ID만 동적으로 조회 (자격 증명 객체 생략)
_, PROJECT_ID = google.auth.default()

DATASET_ID = "thelook_ecommerce"

# 2. BigQuery 클라이언트는 credentials 인자를 제거하여 자동 갱신(Auto-Refresh) 모드로 설정
bq_client = bigquery.Client(project=PROJECT_ID)

try:
    LOCATION = bq_client.get_dataset(DATASET_ID).location
except Exception:
    LOCATION = "us-central1"

# 3. REST API 호출을 위해 공식 AuthorizedSession 초기화
credentials, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
authed_session = AuthorizedSession(credentials)

print(f"Project: {PROJECT_ID}, Dataset: {DATASET_ID}, 리전: {LOCATION}")
print("인프라 및 인증 설정 완료!")

# %% [markdown]
# ## Step 2: API 호출 공통 함수 정의

# %%
# [공통 유틸리티] Knowledge Catalog REST API 전송 함수


def make_rest_request(url, method="GET", body_dict=None, max_retries=5):
    """
    AuthorizedSession을 사용하여 OAuth2 토큰 관리 및 필요한 헤더(x-goog-user-project 등)를 자동으로 처리하여 REST API 통신을 수행합니다.
    429 Quota Exceeded 에러 발생 시 지수 백오프 기반으로 재시도합니다.
    """
    retries = 0
    backoff = 2  # 시작 대기 시간 (초)

    while True:
        try:
            if method == "GET":
                response = authed_session.get(url, timeout=60)
            elif method == "POST":
                response = authed_session.post(url, json=body_dict, timeout=60)
            elif method == "DELETE":
                response = authed_session.delete(url, timeout=60)
            else:
                response = authed_session.request(
                    method, url, json=body_dict, timeout=60
                )

            # API 호출 중 에러가 발생한 경우 상세 에러 응답 바디를 파싱하여 예외를 발생시킵니다.
            if response.status_code >= 400:
                # 429 Quota/Rate Limit 에러 시 지수 백오프 기반 재시도 처리
                if response.status_code == 429 and retries < max_retries:
                    print(
                        f"  [429 Quota Exceeded] {backoff}초 후 재시도 합니다 (재시도: {retries + 1}/{max_retries})..."
                    )
                    time.sleep(backoff)
                    retries += 1
                    backoff *= 2
                    continue
                raise Exception(
                    f"HTTP Error {response.status_code} - {response.text}"
                )

            return response.json()

        except Exception as e:
            if "HTTP Error" in str(e):
                raise e
            # 다른 네트워크 오류인 경우 재시도 처리
            if retries < max_retries:
                time.sleep(backoff)
                retries += 1
                backoff *= 2
                continue
            raise e


# %% [markdown]
# ## Step 3: 데이터셋 DataScan 관리 및 메타데이터 추출

# %%
def get_or_create_dataset_datascan(dataset_id):
    """
    대상 데이터셋에 대해 Gemini 기반의 설명 작성을 지원하는 'DATA_DOCUMENTATION' 타입의 Knowledge Catalog DataScan 리소스를 조회하고, 없으면 새로 생성합니다.
    """
    scan_id = f"ds-{dataset_id}".lower().replace("_", "-")
    get_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}"

    try:
        scan = make_rest_request(get_url, method="GET")
        print(f"  -> 기존 Dataset DataScan 리소스 로드 성공: {scan_id}")
        return scan_id
    except Exception as e:
        if "404" in str(e):
            print(f"  -> 새로운 Dataset DataScan 생성 중: {scan_id}...")
            create_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans?dataScanId={scan_id}"
            body = {
                "data": {
                    # Dataplex DataScan이 빅쿼리 데이터셋을 탐색할 수 있도록 올바른 리소스 경로를 명시합니다.
                    "resource": f"//bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{dataset_id}"
                },
                "executionSpec": {"trigger": {"onDemand": {}}},
                "type": "DATA_DOCUMENTATION",
                "dataDocumentationSpec": {"catalogPublishingEnabled": True},
            }
            operation = make_rest_request(
                create_url, method="POST", body_dict=body
            )
            op_name = operation["name"]

            # 리소스 생성이 완료될 때까지 LRO 상태 폴링 대기
            while True:
                op_status = make_rest_request(
                    f"https://dataplex.googleapis.com/v1/{op_name}",
                    method="GET",
                )
                if op_status.get("done"):
                    if "error" in op_status:
                        raise Exception(
                            f"Dataset DataScan 생성 실패: {op_status['error']}"
                        )
                    break
                time.sleep(2)
            print(f"  -> Dataset DataScan 생성 완료: {scan_id}")
            return scan_id
        else:
            raise e


def run_datascan_and_wait(scan_id):
    """
    Knowledge Catalog DataScan의 실행 Job을 기동하고, 완료될 때까지 주기적으로 상태를 조회(폴링)하여 대기합니다.
    """
    run_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}:run"
    print(f"  -> DataScan 실행 요청 중...")
    run_res = make_rest_request(run_url, method="POST")

    job_name = run_res["job"]["name"]
    job_id = run_res["job"]["uid"]
    print(f"  -> 실행 Job ID: {job_id} (완료 대기 시작...)")

    # # ?view=FULL 파라미터를 추가하여 상세 분석 결과 정보까지 포함해 조회
    job_url = f"https://dataplex.googleapis.com/v1/{job_name}?view=FULL"
    while True:
        job = make_rest_request(job_url, method="GET")
        state = job.get("state")
        print(f"     [폴링] 현재 상태: {state}")

        if state == "SUCCEEDED":
            print("  -> 설명 생성 성공!")
            break
        elif state in ["FAILED", "CANCELLED"]:
            raise Exception(f"DataScan Job 오류 발생: {state}")

        time.sleep(10)


def fetch_dataset_generated_description(dataset_id):
    """
    Knowledge Catalog Entry API를 호출하여 생성된 데이터셋 설명(Descriptions)의 세부 속성(Aspect) 데이터 본문을 조회합니다.
    """
    entry_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{dataset_id}?view=ALL"
    entry_data = make_rest_request(entry_url, method="GET")

    aspects = entry_data.get("aspects", {})
    desc_key = [k for k in aspects.keys() if "descriptions" in k]
    if not desc_key:
        print(
            f"  -> [{dataset_id}] 생성된 설명(Descriptions) Aspect가 존재하지 않습니다."
        )
        return None

    return aspects[desc_key[0]]["data"]


def apply_and_publish_dataset_description(dataset_id, desc_data):
    """
    Knowledge Catalog에서 생성된 한글 설명 메타데이터를 BigQuery 데이터셋 설명으로 복사 동기화하고,
    스캔 결과를 연동하기 위한 공식 시스템 라벨을 데이터셋에 부착합니다.
    """
    if not desc_data:
        return

    dataset_ref = bq_client.dataset(dataset_id)
    dataset = bq_client.get_dataset(dataset_ref)

    # 1. 데이터셋 설명 업데이트
    dataset.description = desc_data.get("description", dataset.description)

    # 2. 공식 데이터 설명 퍼블리싱 라벨 추가 (데이터셋 라벨)
    labels = dict(dataset.labels or {})
    scan_id = f"ds-{dataset_id}".lower().replace("_", "-")
    labels["dataplex-data-documentation-published-scan"] = scan_id
    labels["dataplex-data-documentation-published-project"] = PROJECT_ID
    labels["dataplex-data-documentation-published-location"] = LOCATION
    dataset.labels = labels

    # 3. BigQuery에 설명 및 라벨 업데이트 전송
    bq_client.update_dataset(dataset, ["description", "labels"])
    print(f"  [SUCCESS] {dataset_id} 데이터셋 설명 주입 완료!")


# %% [markdown]
# ## Step 4: 메타데이터 추출 및 BigQuery 동기화

# %%
# 메인 실행 파이프라인
print(f"=== 데이터셋 설명 자동화 시작: {DATASET_ID} ===")

# 0. 언어 지침 주입 (Language Directive)
# Gemini 모델이 데이터셋 설명을 한국어로 작성하도록 데이터셋의 기존 설명에 지침을 미리 삽입합니다.
dataset_ref = bq_client.dataset(DATASET_ID)
dataset = bq_client.get_dataset(dataset_ref)
dataset.description = "Generate dataset descriptions using the Korean language"
bq_client.update_dataset(dataset, ["description"])
print(f"  -> {DATASET_ID} 데이터셋에 한국어 작성 지침 주입 완료.")

# 1. Dataset DataScan 생성 또는 로드
scan_id = get_or_create_dataset_datascan(DATASET_ID)

# 2. DataScan 실행 및 완료 대기
run_datascan_and_wait(scan_id)

# 3. 생성된 설명 메타데이터 조회
desc_data = fetch_dataset_generated_description(DATASET_ID)

if desc_data:
    print(f"\n[생성된 데이터셋 설명 요약]")
    print(f" - 설명: {desc_data.get('description')}")

    # 4. BigQuery 데이터셋에 설명 및 라벨 반영
    apply_and_publish_dataset_description(DATASET_ID, desc_data)
else:
    print("설명 데이터를 가져오지 못했습니다.")

print(f"\n=== 데이터셋 설명 자동화 완료: {DATASET_ID} ===")

# %% [markdown]
# ## Step 5: 실행 후 콘솔 UI 및 관계 네트워크 검증
#
# 노트북 실행 완료 후, BigQuery Studio 콘솔에서 `thelook_ecommerce` 데이터셋의 **Insights** 탭을 새로고침하여 다음 항목을 검토합니다:
#
# ### 1. Dataset description (데이터셋 종합 비즈니스 요약)
# - 상단에 이커머스 플랫폼의 전반적인 운영 흐름(사용자 활동, 주문 생성 및 배송, 인벤토리 관리 및 물류센터 적재)을 포괄하는 비즈니스 레벨의 요약문이 생성됩니다.
#
# ### 2. Relationships 다이어그램 (테이블 관계 네트워크 시각화)
# - **7 Nodes & 9 Edges**: `users`, `orders`, `order_items`, `products`, `events`, `inventory_items`, `distribution_centers` 7개 테이블이 유기적인 연결선(Edge)으로 시각화됩니다.
# - 노드를 클릭하여 드래그하거나 확대/축소하며 테이블 간의 연결 구조를 직관적으로 파악할 수 있습니다.
#
# ### 3. Relationship Table (추론된 관계 명세표)
# 하단 테이블에 LLM이 추론한 각 테이블 간의 조인 키 및 외래키 관계가 상세히 나열됩니다:
# - `distribution_centers` <-> `products`: `distribution_centers.id = products.distribution_center_id` (Source: `LLM-inferred`)
# - `order_items` <-> `users`: `order_items.user_id = users.id` (Source: `LLM-inferred`)
# - `orders` <-> `users`: `orders.user_id = users.id` (Source: `LLM-inferred`)
# - `order_items` <-> `products`: `order_items.product_id = products.id` (Source: `LLM-inferred`)
#
# 이 관계 구조는 추후 대화형 분석 에이전트가 복잡한 다중 테이블 조인 쿼리를 생성할 때 오답(Hallucination) 없이 정확한 SQL을 작성하도록 돕는 핵심 지식 소스가 됩니다.
#
