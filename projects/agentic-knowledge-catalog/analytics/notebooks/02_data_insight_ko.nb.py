# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% id="82836355"
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

# %% [markdown] id="238c405e"
# # BigQuery Data Insights 기반 테이블 및 컬럼 설명 자동 적재
#
# 본 노트북은 **Gemini in BigQuery (Data Insights)** 자동화 API를 사용하여, `thelook_ecommerce` 데이터셋 내 모든 테이블과 컬럼에 대한 한국어 설명을 자동으로 생성하고 BigQuery 카탈로그에 동기화합니다.
#
# ### 학습 목표
# 1. **데이터 인사이트(Data Insights)**: LLM을 활용하여 원천 데이터의 의미와 스키마를 요약하는 한글 설명을 자동 생성합니다.
# 2. **카탈로그 자동 게시(Publishing)**: 생성된 설명 메타데이터를 BigQuery 테이블 상세 정보(Description) 및 컬럼 설명에 주입합니다.
# 3. **추천 분석 쿼리(Recommended Queries)**: 데이터 특성에 부합하는 심층 분석 SQL 쿼리를 자동으로 도출합니다.
# 4. **거버넌스 라벨링**: 작업 성공 여부와 스캔 리전 정보(`dataplex-dp-*`, `dataplex-dq-*`, `dataplex-data-*-published-*`)를 테이블 라벨(Labels)로 연동 관리합니다.
#
# ---
#
# ### [실행 전 콘솔 UI 확인]
# 노트북을 실행하기 전, BigQuery Studio 콘솔에서 `thelook_ecommerce` > `users` 테이블을 선택해 보세요:
# - **Schema 탭**: 각 컬럼의 Description(설명) 필드가 모두 비어 있습니다.
# - **Insights 탭**: "Insights have not yet been generated" 안내 문구와 함께 생성된 인사이트가 없는 상태입니다.
#

# %% [markdown] id="c62f90c4"
# ## Step 1: 환경 초기화

# %% id="391f2a80"
# [Qwiklabs 환경 대응] 만약 Dataplex API 호출 중 HTTP Error 401 (Invalid authentication credentials) 에러가 발생한다면,
# 아래 줄의 주석을 해제하고 실행하여 1회성 수동 인증(ADC 생성)을 수행해 주세요.
# # !gcloud auth application-default login --no-launch-browser --quiet

import json
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

# %% [markdown] id="f7791da4"
# ## Step 2: API 호출 공통 함수 정의

# %% id="5af169f8"
# [공통 유틸리티] Knowledge Catalog REST API 전송 함수


def make_rest_request(url, method="GET", body_dict=None, max_retries=5):
    """
    AuthorizedSession을 사용하여 OAuth2 토큰 관리 및 필요한 헤더(x-goog-user-project 등)를 자동으로 처리하여 REST API 통신을 수행합니다.
    429 Quota Exceeded 발생 시 지수 백오프 기반으로 재시도합니다.
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


# %% [markdown] id="e918d816"
# ## Step 3: Knowledge Catalog DataScan 관리 및 모니터링 모듈 정의

# %% id="a0303cad"
def get_or_create_datascan(table_id):
    """
    대상 테이블에 대해 Gemini 기반의 설명 작성을 지원하는 'DATA_DOCUMENTATION' 타입의 Knowledge Catalog DataScan 리소스를 조회하고, 없으면 새로 생성합니다.
    이때 catalogPublishingEnabled 옵션을 True로 지정하여 생성된 설명이 카탈로그에 자동 게시되도록 구성합니다.
    """
    scan_id = f"ds-thelook-{table_id}".lower().replace("_", "-")
    get_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}"

    try:
        scan = make_rest_request(get_url, method="GET")
        print(
            f"  -> 기존 Knowledge Catalog DataScan 리소스 로드 성공: {scan_id}"
        )
        return scan_id
    except Exception as e:
        if "404" in str(e):
            print(
                f"  -> 새로운 Knowledge Catalog DataScan 생성 중: {scan_id}..."
            )
            create_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans?dataScanId={scan_id}"
            body = {
                "data": {
                    "resource": f"//bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DATASET_ID}/tables/{table_id}"
                },
                "executionSpec": {"trigger": {"onDemand": {}}},
                "type": "DATA_DOCUMENTATION",
                "dataDocumentationSpec": {
                    "generationScopes": "ALL",
                    "catalogPublishingEnabled": True,
                },
            }
            operation = make_rest_request(
                create_url, method="POST", body_dict=body
            )
            op_name = operation["name"]

            while True:
                op_status = make_rest_request(
                    f"https://dataplex.googleapis.com/v1/{op_name}",
                    method="GET",
                )
                if op_status.get("done"):
                    if "error" in op_status:
                        raise Exception(
                            f"Knowledge Catalog DataScan 생성 실패: {op_status['error']}"
                        )
                    break
                time.sleep(2)
            print(f"  -> Knowledge Catalog DataScan 생성 완료: {scan_id}")
            return scan_id
        else:
            raise e


def run_datascan_and_wait(scan_id):
    """
    Knowledge Catalog DataScan의 실행 Job을 기동하고, 완료될 때까지 주기적으로 상태를 조회(폴링)하여 대기합니다.
    (단일 테이블 테스트 검증 단계에서 사용됩니다.)
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


def trigger_datascan(scan_id):
    """
    Knowledge Catalog DataScan의 실행 Job을 구동하고 완료 대기 없이 Job 리소스 이름을 즉시 반환합니다.
    (전체 테이블 일괄 비동기 실행 파이프라인에서 사용됩니다.)
    """
    run_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/dataScans/{scan_id}:run"
    run_res = make_rest_request(run_url, method="POST")
    return run_res["job"]["name"]


# %% [markdown] id="7e726ccd"
# ## Step 4: 메타데이터 추출 및 BigQuery 동기화 적용 모듈 정의

# %% id="c14cb5e1"
def fetch_generated_descriptions(table_id):
    """
    Knowledge Catalog Entry API를 호출하여 생성된 스키마 설명(Descriptions)의 세부 속성(Aspect) 데이터 본문을 조회합니다.
    (반드시 view=ALL 파라미터를 사용하여 GET 호출을 날려야 세부 Aspect 본문 데이터가 리턴됩니다.)
    """
    entry_url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DATASET_ID}/tables/{table_id}?view=ALL"
    entry_data = make_rest_request(entry_url, method="GET")

    aspects = entry_data.get("aspects", {})
    desc_key = [k for k in aspects.keys() if "descriptions" in k]
    if not desc_key:
        print(
            f"  -> [{table_id}] 생성된 설명(Descriptions) Aspect가 존재하지 않습니다."
        )
        return None

    return aspects[desc_key[0]]["data"]


def apply_and_publish_descriptions(table_id, desc_data):
    """
    Knowledge Catalog에서 생성된 한글 설명 메타데이터를 BigQuery 테이블 및 개별 컬럼 설명으로 복사 동기화하고,
    스캔 결과를 연동하기 위한 공식 시스템 라벨을 테이블에 부착합니다.
    """
    if not desc_data:
        return

    table_ref = bq_client.dataset(DATASET_ID).table(table_id)
    table = bq_client.get_table(table_ref)

    # 1. 테이블 설명 업데이트
    table.description = desc_data.get("description", table.description)

    # 2. 컬럼 설명 업데이트
    fields_desc = {
        f["name"]: f["description"] for f in desc_data.get("fields", [])
    }
    new_schema = []

    for field in table.schema:
        description = fields_desc.get(field.name, field.description)
        new_field = bigquery.SchemaField(
            name=field.name,
            field_type=field.field_type,
            mode=field.mode,
            description=description,
            fields=field.fields,
        )
        new_schema.append(new_field)

    table.schema = new_schema

    # 3. 공식 데이터 설명 퍼블리싱 라벨 추가 (빅쿼리 표준 라벨 형식)
    # 아래 라벨 정보들은 BigQuery Studio 콘솔 UI와 Knowledge Catalog의 자동 동기화를 지원하기 위해 활용됩니다.
    labels = dict(table.labels or {})
    scan_id = f"ds-thelook-{table_id}".lower().replace("_", "-")
    labels["dataplex-data-documentation-published-scan"] = scan_id
    labels["dataplex-data-documentation-published-project"] = PROJECT_ID
    labels["dataplex-data-documentation-published-location"] = LOCATION
    table.labels = labels

    # 4. BigQuery에 스키마, 설명, 라벨 업데이트 전송 및 물리 반영
    bq_client.update_table(table, ["description", "schema", "labels"])
    print(f"  [SUCCESS] {table_id} 테이블 및 컬럼 설명 주입 완료!")


# %% [markdown] id="a0060963"
# ## Step 5: 단일 테이블 테스트 배포 검증

# %% id="13be97e6"
# 검증용 테스트 테이블: distribution_centers
TEST_TABLE = "distribution_centers"

print(f"=== [{TEST_TABLE}] 데이터 인사이트 기반 설명 생성 테스트 시작 ===")

# 1. 기존 한글 설명 컬럼 초기화 (None 상태로 리셋 및 한국어 지침 주입)
# 테스트를 위해 기존 설명을 비우고, 테이블 설명에 언어 지침을 명시합니다.
t_ref = bq_client.dataset(DATASET_ID).table(TEST_TABLE)
table = bq_client.get_table(t_ref)
table.description = (
    "Generate table and column descriptions using the Korean language"
)
new_schema = []
for field in table.schema:
    new_schema.append(
        bigquery.SchemaField(
            name=field.name,
            field_type=field.field_type,
            mode=field.mode,
            description=None,
            fields=field.fields,
        )
    )
table.schema = new_schema
bq_client.update_table(table, ["description", "schema"])
print(f"  -> {TEST_TABLE} 컬럼 설명 초기화 완료 (테스트 준비 완료)")

# 2. Knowledge Catalog DataScan 리소스 로드 또는 생성
scan_id = get_or_create_datascan(TEST_TABLE)

# 3. Knowledge Catalog DataScan 실행 및 완료 대기 (약 1분 소요)
run_datascan_and_wait(scan_id)

# 4. Knowledge Catalog Aspect에서 생성된 설명 가져오기
desc_data = fetch_generated_descriptions(TEST_TABLE)

# 5. BigQuery 주입 적재 및 공식 라벨 부착
apply_and_publish_descriptions(TEST_TABLE, desc_data)

print(
    "\n테스트 완료! 빅쿼리 콘솔에서 해당 테이블의 스키마와 한글 설명을 확인해보세요."
)

# %% [markdown] id="8abee0ce"
# ## Step 6: 일괄 실행 파이프라인

# %% id="48cfb403"
# [메인 실행 파이프라인] 전체 테이블 대상 데이터 인사이트 일괄 실행
# 전체 대상 테이블들을 차례대로 비동기(Async) 병렬로 기동한 뒤, 요약 모니터링을 진행하고 한 번에 빅쿼리에 적재합니다.

ALL_TABLES = [
    "users",
    "orders",
    "order_items",
    "products",
    "events",
    "inventory_items",
]

print(
    "=== [전체 데이터셋 대상 Data Insights 한글 생성 일괄 파이프라인 기동 (비동기)] ==="
)

active_jobs = {}  # {job_name: table_id}

for t_id in ALL_TABLES:
    print(
        f"\n=====================[ {t_id} 준비 및 기동 ]====================="
    )
    try:
        # 1. 언어 지침(Korean Language Guide) 테이블 설명란에 주입
        t_ref = bq_client.dataset(DATASET_ID).table(t_id)
        table = bq_client.get_table(t_ref)
        table.description = (
            "Generate table and column descriptions using the Korean language"
        )
        bq_client.update_table(table, ["description"])

        # 2. Knowledge Catalog DataScan 리소스 조회 혹은 신규 생성
        scan_id = get_or_create_datascan(t_id)

        # 3. 비동기 실행 트리거 및 관리 등록
        job_name = trigger_datascan(scan_id)
        active_jobs[job_name] = t_id

        print(f"  -> '{t_id}' 테이블 설명 생성 Job 기동 완료.")

        # API 할당량(Quota) 초과 방지를 위한 기동 지연 시간 추가
        time.sleep(3)

    except Exception as e:
        print(f"  [오류 발생] '{t_id}' 테이블 기동 실패: {e}")

total_triggered = len(active_jobs)
print(
    f"\n총 {total_triggered}개의 데이터 인사이트 스캔 작업이 동시에 기동되었습니다. 진행 상황 모니터링을 시작합니다."
)
print(
    "(개별 작업 완료 시 알림이 출력되며, 30초 주기로 전체 현황을 요약 출력합니다.)\n"
)

# 간결한 진행 상태 모니터링 루프
completed_tables = []  # 완료된 테이블 ID 리스트

while active_jobs:
    status_summary = {
        "PENDING": 0,
        "RUNNING": 0,
        "SUCCEEDED": 0,
        "FAILED": 0,
        "CANCELLED": 0,
    }

    # 각 실행 작업들의 현재 상태 폴링 조회
    for job_name in list(active_jobs.keys()):
        job_url = f"https://dataplex.googleapis.com/v1/{job_name}"
        try:
            job = make_rest_request(job_url, method="GET")
            state = job.get("state", "UNKNOWN")

            status_summary[state] = status_summary.get(state, 0) + 1

            if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                t_id = active_jobs[job_name]
                print(f"  [완료] '{t_id}' 설명 생성 완료 (결과: {state})")

                # 정상적으로 성공한 경우 완료 목록에 테이블 ID 저장
                if state == "SUCCEEDED":
                    completed_tables.append(t_id)

                del active_jobs[job_name]
        except Exception as e:
            # 일시적인 API 오류 등은 로깅 후 바이패스하고 다음 주기 재시도
            pass

    if active_jobs:
        running_cnt = status_summary.get("RUNNING", 0) + status_summary.get(
            "PENDING", 0
        )
        succeeded_cnt = (
            total_triggered
            - len(active_jobs)
            - status_summary.get("FAILED", 0)
            - status_summary.get("CANCELLED", 0)
        )

        print(
            f"[진행 상태] 진행 중: {running_cnt}개 | 완료: {succeeded_cnt}개 | 실패: {status_summary.get('FAILED', 0)}개",
            end="\r",
        )
        time.sleep(30)  # 쿼터 초과 방지를 위한 30초 대기

print(
    "\n\n=== [모든 테이블 설명 생성 완료. 빅쿼리 메타데이터 동기화 및 적재를 시작합니다.] ==="
)

# 4 & 5. 완료된 각 테이블의 최종 결과 로드 및 빅쿼리 적재 실행
for t_id in completed_tables:
    try:
        print(f" -> [{t_id}] 생성 결과 조회 및 빅쿼리 스키마 반영 중...")
        desc_data = fetch_generated_descriptions(t_id)
        apply_and_publish_descriptions(t_id, desc_data)
    except Exception as e:
        print(f"  [오류] [{t_id}] 스키마 반영 실패: {e}")

print(
    "\n=== [전체 테이블 데이터 인사이트 한글 생성 및 빅쿼리 적재 파이프라인 최종 완료] ==="
)

# %% [markdown]
# ## Step 5: 실행 후 콘솔 UI 및 메타데이터 검증
#
# 노트북 실행이 완료되면 BigQuery Studio 콘솔에서 `users` 테이블을 다시 확인하여 다음 사항을 검토합니다:
#
# ### 1. 스키마 및 컬럼 한글 설명 반영 확인
# - **Table description**: "이 테이블은 전자상거래 플랫폼 사용자들에 대한 정보를 담고 있습니다. 여기에는 개인 식별 정보, 연락처 세부 정보, 지리적 위치 데이터 및 사용자 행동 관련 정보가 포함됩니다..."라는 한글 요약이 상단에 표시됩니다.
# - **View column descriptions**: `id`, `first_name`, `email`, `age`, `gender` 등 각 컬럼에 한글 상세 설명이 주입됩니다.
#
# ### 2. Insights 탭 추천 분석 쿼리 검토
# `users` 테이블의 **Insights** 탭으로 이동하면 다음과 같은 유용한 심층 분석 SQL이 자동 생성된 것을 확인할 수 있습니다:
# - **추천 쿼리 1**: 특정 트래픽 소스에서 유입된 사용자들의 연령과 위도 간의 공분산 계산 쿼리
# - **추천 쿼리 2**: 사용자 생성 시간에 따른 연령과 경도 간 피어슨 상관 계수 분석 쿼리
#
# ### 3. 세부정보(Details) 탭 메타데이터 라벨 확인
# - **Description**: 주입된 테이블 한글 설명이 영구 메타데이터로 표시됩니다.
# - **Labels 항목**:
#   - `dataplex-dp-published-scan`: `dp-thelook-users` (BigQuery Studio의 **Data Profile** 탭 연동)
#   - `dataplex-dq-published-scan`: `dq-thelook-users` (BigQuery Studio의 **Data Quality** 탭 연동)
#   - `dataplex-data-documentation-published-scan`: 생성된 Data Documentation 스캔 ID
#   - `dataplex-*-published-location`: 배포 리전
#   - `dataplex-*-published-project`: 프로젝트 ID
#   - 거버넌스 파이프라인의 작업 결과가 테이블 라벨로 연동되어 게시(Publish) 상태가 자동으로 증명됩니다.
#
