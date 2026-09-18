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
# # TheLook 쇼핑몰 비즈니스 용어집 구축 및 대화형 에이전트 검증
#
# 본 노트북은 자연어 질문을 BigQuery SQL로 정확히 변환할 수 있도록 **Knowledge Catalog 비즈니스 용어집(Business Glossary)**과 **SQL 매핑 Aspect(애스펙트)**를 구축하고, 이를 바탕으로 **BigQuery 대화형 분석 에이전트(Conversational Agent)**를 생성하여 거버넌스 효과를 직접 검증합니다.
#
# ### 학습 목표
# 1. **용어집 구조 이해**: 비즈니스 용어(Term), 카테고리(Category) 간 계층 구조를 이해하고 Knowledge Catalog에 등록합니다.
# 2. **커스텀 Aspect 등록**: 자연어를 SQL 규칙으로 매핑하기 위한 `sql-mapping` Aspect를 정의합니다.
# 3. **물리 리소스 연동**: 비즈니스 용어와 실제 BigQuery 물리 테이블 및 컬럼을 상호 연계합니다.
# 4. **대화형 에이전트 검증**: 구축된 비즈니스 용어집과 Aspect를 지식 소스로 활용하여, 에이전트가 모호한 비즈니스 개념('우수 고객')을 정확한 SQL 서브쿼리로 변환하는지 실습합니다.
#

# %% [markdown]
# ## Step 1: 초기 환경 설정 및 REST API 설정

# %%
# [Qwiklabs 환경 대응] 만약 Dataplex API 호출 중 HTTP Error 401 (Invalid authentication credentials) 에러가 발생한다면,
# 아래 줄의 주석을 해제하고 실행하여 1회성 수동 인증(ADC 생성)을 수행해 주세요.
# # !gcloud auth application-default login --no-launch-browser --quiet

import json
import ssl
import subprocess
import time
import urllib.error
import urllib.request

import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from google.cloud import bigquery

# 1. 설정 정보 정의
GLOSSARY_ID = "thelook-glossary"

# 2. Google Cloud 프로젝트 ID 조회 및 Access Token 발급
credentials, PROJECT_ID = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
authed_session = AuthorizedSession(credentials)

bq_client = bigquery.Client(project=PROJECT_ID)
try:
    LOCATION = bq_client.get_dataset("thelook_ecommerce").location
except Exception:
    LOCATION = "us-central1"

REINITIALIZE = (
    False  # True 설정 시 기존 용어집 자원을 전체 삭제 후 초기화 구축합니다.
)

# REST API를 사용하여 프로젝트 번호(Project Number) 조회
response = authed_session.get(
    f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}"
)
PROJECT_NUMBER = response.json()["projectNumber"]

print(
    f"Google Cloud Project ID: {PROJECT_ID} (Project Number: {PROJECT_NUMBER})"
)

# %% [markdown]
# ## Step 2: API 호출 공통 함수 정의

# %%
existing_categories = None

# ==========================================
# [공통] 지수 백오프 및 재시도 내장 REST 요청 헬퍼
# ==========================================


def send_rest_request_with_retry(
    url,
    method="POST",
    body=None,
    max_attempts=5,
    ignore_409=True,
    retry_on_403_404=False,
):
    """백오프 및 특정 HTTP 에러 대응 로직을 중앙 집중화한 REST API 요청 공통 함수입니다."""
    backoff = 2

    for attempt in range(max_attempts):
        try:
            if method == "GET":
                response = authed_session.get(url, timeout=60)
            elif method == "POST":
                response = authed_session.post(url, json=body, timeout=60)
            elif method == "PATCH":
                response = authed_session.patch(url, json=body, timeout=60)
            elif method == "DELETE":
                response = authed_session.delete(url, timeout=60)
            else:
                response = authed_session.request(
                    method, url, json=body, timeout=60
                )

            if response.status_code < 400:
                return True

            # 409 Conflict: 이미 존재하는 리소스인 경우 성공으로 간주
            if response.status_code == 409 and ignore_409:
                return True
            # 429 Rate Limit: 지수 백오프 대기 후 재시도
            elif response.status_code == 429:
                print(
                    f"    [WAIT] 호출 제한(429)으로 인해 대기 후 재시도합니다. (시도 {attempt+1}/{max_attempts})..."
                )
                time.sleep(backoff)
                backoff *= 2
            # 403/404: 인덱싱 미반영 대기
            elif response.status_code in (403, 404) and retry_on_403_404:
                print(
                    f"    [WAIT] 인덱싱 반영 대기 중... 5초 후 재시도합니다. (시도 {attempt+1}/{max_attempts})"
                )
                time.sleep(5)
            else:
                print(
                    f"    [FAIL] API 호출 실패: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            print(f"    [FAIL] API 호출 중 오류 발생: {e}")
            if attempt < max_attempts - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                return False

    print(f"    [FAIL] API 호출 실패 (최대 시도 횟수 초과)")
    return False


# ==========================================
# 개별 리소스 관리 및 연동 함수
# ==========================================


# 1. 카테고리 생성 (gcloud CLI 기반)
def get_or_create_category(cat_id, display_name, parent_path):
    global existing_categories
    if existing_categories is None:
        existing_categories = set()
        list_cats = subprocess.run(
            [
                "gcloud",
                "dataplex",
                "glossaries",
                "categories",
                "list",
                f"--glossary={GLOSSARY_ID}",
                f"--location={LOCATION}",
                f"--project={PROJECT_ID}",
                "--format=value(name)",
            ],
            capture_output=True,
            text=True,
        )
        if list_cats.returncode == 0 and list_cats.stdout.strip():
            for cat_path in list_cats.stdout.strip().split("\n"):
                existing_categories.add(cat_path.split("/")[-1])
        print(
            f"기존 등록 카테고리 캐싱 완료 (기존 카테고리: {len(existing_categories)}개)"
        )

    if cat_id not in existing_categories:
        print(f"카테고리 생성 중: {cat_id} ({display_name})...")
        subprocess.run(
            [
                "gcloud",
                "dataplex",
                "glossaries",
                "categories",
                "create",
                cat_id,
                f"--glossary={GLOSSARY_ID}",
                f"--location={LOCATION}",
                f"--project={PROJECT_ID}",
                f"--parent={parent_path}",
                f"--display-name={display_name}",
            ],
            check=True,
        )
        existing_categories.add(cat_id)
        print(f"  카테고리 생성 성공: {cat_id}. 인덱싱 대기 (3초)...")
        time.sleep(3)
    return f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/categories/{cat_id}"


# 2. 용어 생성


def create_glossary_term(term_id, display_name, description, parent_path):
    url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms?termId={term_id}"
    body = {
        "displayName": display_name,
        "description": description,
        "parent": parent_path,
    }
    return send_rest_request_with_retry(url, method="POST", body=body)


# 3. 테이블 연동


def link_term_to_table(term_entry_path, bq_entry_path, link_id):
    url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@bigquery/entryLinks?entry_link_id={link_id}"
    body = {
        "entryLinkType": "projects/dataplex-types/locations/global/entryLinkTypes/definition",
        "entryReferences": [
            {"name": bq_entry_path, "type": "SOURCE"},
            {"name": term_entry_path, "type": "TARGET"},
        ],
    }
    return send_rest_request_with_retry(url, method="POST", body=body)


# 4. 연관 용어 상호 연동


def link_related_terms(term_1_path, term_2_path, link_id):
    url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entryLinks?entry_link_id={link_id}"
    body = {
        "entryLinkType": "projects/dataplex-types/locations/global/entryLinkTypes/related",
        "entryReferences": [
            {"name": term_1_path, "type": "UNSPECIFIED"},
            {"name": term_2_path, "type": "UNSPECIFIED"},
        ],
    }
    return send_rest_request_with_retry(url, method="POST", body=body)


# 5. 동의어 상호 연동


def link_synonym_terms(term_1_path, term_2_path, link_id):
    url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entryLinks?entry_link_id={link_id}"
    body = {
        "entryLinkType": "projects/dataplex-types/locations/global/entryLinkTypes/synonym",
        "entryReferences": [
            {"name": term_1_path, "type": "UNSPECIFIED"},
            {"name": term_2_path, "type": "UNSPECIFIED"},
        ],
    }
    return send_rest_request_with_retry(url, method="POST", body=body)


# 6. 커스텀 Aspect Type 생성 (sql-mapping)


def create_sql_mapping_aspect_type():
    aspect_type_id = "sql-mapping"
    print(f"Aspect Type 등록 확인 중: {aspect_type_id}...")

    # 1. 기존 등록 여부 확인
    check_cmd = subprocess.run(
        [
            "gcloud",
            "dataplex",
            "aspect-types",
            "describe",
            aspect_type_id,
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
            "--format=value(name)",
        ],
        capture_output=True,
        text=True,
    )
    if check_cmd.returncode == 0 and check_cmd.stdout.strip():
        print(f"  이미 등록된 Aspect Type입니다: {aspect_type_id}")
        return True

    # 2. REST API로 생성 시도 (recordFields 내 index 필수 정의)
    url = f"https://dataplex.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/aspectTypes?aspectTypeId={aspect_type_id}"
    body = {
        "displayName": "SQL Mapping Ruleset",
        "description": "SQL mapping ruleset for Text-to-SQL data agents",
        "metadataTemplate": {
            "name": "sql_mapping",
            "type": "record",
            "recordFields": [
                {
                    "name": "type",
                    "type": "string",
                    "index": 1,
                    "constraints": {"required": True},
                },
                {"name": "table", "type": "string", "index": 2},
                {"name": "condition", "type": "string", "index": 3},
                {"name": "expression", "type": "string", "index": 4},
                {"name": "attribute", "type": "string", "index": 5},
            ],
        },
    }
    if send_rest_request_with_retry(url, method="POST", body=body):
        print(f"  Aspect Type 등록 성공 (REST API): {aspect_type_id}")
        return True

    # 3. REST 실패 시 gcloud CLI 폴백
    print(
        f"  [안내] REST API 등록 실패, gcloud CLI로 생성을 재시도합니다: {aspect_type_id}..."
    )
    import tempfile

    template_content = {
        "name": "sql_mapping",
        "type": "record",
        "recordFields": [
            {
                "name": "type",
                "type": "string",
                "index": 1,
                "constraints": {"required": True},
            },
            {"name": "table", "type": "string", "index": 2},
            {"name": "condition", "type": "string", "index": 3},
            {"name": "expression", "type": "string", "index": 4},
            {"name": "attribute", "type": "string", "index": 5},
        ],
    }
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(template_content, tmp)
            tmp_path = tmp.name
        res = subprocess.run(
            [
                "gcloud",
                "dataplex",
                "aspect-types",
                "create",
                aspect_type_id,
                f"--location={LOCATION}",
                f"--project={PROJECT_ID}",
                f"--metadata-template-file-name={tmp_path}",
                "--display-name=SQL Mapping Ruleset",
                "--description=SQL mapping ruleset for Text-to-SQL data agents",
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print(f"  Aspect Type 등록 성공 (gcloud CLI): {aspect_type_id}")
            return True
        else:
            print(f"  [FAIL] gcloud Aspect Type 생성 실패: {res.stderr.strip()}")
            return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# 7. 용어 Entry에 Aspect 첨부


def attach_aspect_to_term(term_entry_path, aspect_data):
    aspect_type_path = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}/aspectTypes/sql-mapping"
    )
    aspect_key = f"{PROJECT_ID}.{LOCATION}.sql-mapping"
    url = f"https://dataplex.googleapis.com/v1/{term_entry_path}?update_mask=aspects&aspect_keys={aspect_key}"
    body = {
        "aspects": {
            aspect_key: {"aspect_type": aspect_type_path, "data": aspect_data}
        }
    }
    return send_rest_request_with_retry(
        url, method="PATCH", body=body, retry_on_403_404=True
    )


# %% [markdown]
# ## Step 3: 기존 비즈니스 용어집 정리

# %%
def cleanup_glossary_if_exists():
    describe_glossary = subprocess.run(
        [
            "gcloud",
            "dataplex",
            "glossaries",
            "describe",
            GLOSSARY_ID,
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
        ],
        capture_output=True,
        text=True,
    )
    if describe_glossary.returncode != 0:
        print(f"Glossary '{GLOSSARY_ID}'가 존재하지 않습니다. 새로 생성합니다.")
        return

    print(
        f"기존 Glossary '{GLOSSARY_ID}' 발견. 재생성을 위해 하위 요소를 역순으로 정리합니다..."
    )

    # A. 모든 용어(Terms) 삭제
    terms_proc = subprocess.run(
        [
            "gcloud",
            "dataplex",
            "glossaries",
            "terms",
            "list",
            f"--glossary={GLOSSARY_ID}",
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
            "--format=value(name)",
        ],
        capture_output=True,
        text=True,
    )

    if terms_proc.stdout.strip():
        for term_path in terms_proc.stdout.strip().split("\n"):
            term_id = term_path.split("/")[-1]
            print(f"  용어 삭제 중: {term_id}...")
            subprocess.run(
                [
                    "gcloud",
                    "dataplex",
                    "glossaries",
                    "terms",
                    "delete",
                    term_id,
                    f"--glossary={GLOSSARY_ID}",
                    f"--location={LOCATION}",
                    f"--project={PROJECT_ID}",
                    "--quiet",
                ],
                check=True,
            )

    # B. 모든 카테고리(Categories) 삭제
    cats_proc = subprocess.run(
        [
            "gcloud",
            "dataplex",
            "glossaries",
            "categories",
            "list",
            f"--glossary={GLOSSARY_ID}",
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
            "--format=value(name)",
        ],
        capture_output=True,
        text=True,
    )

    if cats_proc.stdout.strip():
        cats = cats_proc.stdout.strip().split("\n")
        cats.sort(key=len, reverse=True)
        for cat_path in cats:
            cat_id = cat_path.split("/")[-1]
            print(f"  카테고리 삭제 중: {cat_id}...")
            subprocess.run(
                [
                    "gcloud",
                    "dataplex",
                    "glossaries",
                    "categories",
                    "delete",
                    cat_id,
                    f"--glossary={GLOSSARY_ID}",
                    f"--location={LOCATION}",
                    f"--project={PROJECT_ID}",
                    "--quiet",
                ],
                check=True,
            )

    # C. 용어집(Glossary) 본체 삭제
    print(f"용어집 본체 삭제 중: {GLOSSARY_ID}...")
    subprocess.run(
        [
            "gcloud",
            "dataplex",
            "glossaries",
            "delete",
            GLOSSARY_ID,
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
            "--quiet",
        ],
        check=True,
    )
    print(
        "기존 용어집 정리 완료. 안정적인 카탈로그 동기화를 위해 10초간 대기합니다..."
    )
    time.sleep(10)


# REINITIALIZE 플래그에 따라 작동 선택
if REINITIALIZE:
    cleanup_glossary_if_exists()
else:
    print(
        "REINITIALIZE 플래그가 False입니다. 기존 용어집 정리를 건너뛰고 증분 모드로 진행합니다."
    )

# %% [markdown]
# ## Step 4: 신규 비즈니스 용어집 생성

# %%
# Glossary 존재 확인 헬퍼 함수


def check_glossary_exists():
    describe_glossary = subprocess.run(
        [
            "gcloud",
            "dataplex",
            "glossaries",
            "describe",
            GLOSSARY_ID,
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
        ],
        capture_output=True,
        text=True,
    )
    return describe_glossary.returncode == 0


# 존재하지 않을 경우에만 생성 진행
if not check_glossary_exists():
    print(f"\n새로운 Glossary '{GLOSSARY_ID}'를 생성합니다...")
    subprocess.run(
        [
            "gcloud",
            "dataplex",
            "glossaries",
            "create",
            GLOSSARY_ID,
            f"--location={LOCATION}",
            f"--project={PROJECT_ID}",
            "--description=TheLook Ecommerce Business Glossary with Taxonomy",
            "--display-name=TheLook Glossary",
        ],
        check=True,
    )
    print(
        "용어집 생성 완료. 카탈로그 인덱싱 동기화를 위해 15초간 대기합니다..."
    )
    time.sleep(15)
else:
    print(f"Glossary '{GLOSSARY_ID}'가 이미 존재합니다. 생성을 건너뜁니다.")

# %% [markdown]
# ## Step 5: 비즈니스 용어 정의 데이터셋 로드

# %%
# GCS 버킷 및 파일 경로 정의
RESOURCE_BUCKET = f"metadata-resources-{PROJECT_ID}"
GCS_BLOB_PATH = "resources/business_glossary_ko.json"
LOCAL_GLOSSARY_PATH = "../resources/business_glossary_ko.json"

import json
import os

from google.cloud import storage

# 로컬 파일이 존재하는 경우 우선적으로 로드 (로컬 개발 및 수정 테스트 시 유용)
if os.path.exists(LOCAL_GLOSSARY_PATH) or os.path.exists("../resources/business_glossary.json"):
    print(f"로컬 파일 발견. 로컬 경로에서 용어집을 로드합니다: {LOCAL_GLOSSARY_PATH}")
    actual_local = LOCAL_GLOSSARY_PATH if os.path.exists(LOCAL_GLOSSARY_PATH) else "../resources/business_glossary.json"
    with open(actual_local, "r", encoding="utf-8") as f:
        glossary_data = json.load(f)

# 로컬 파일이 없는 경우 (예: Colab 원격 실습 환경) -> GCS에서 다운로드하여 로드
else:
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(RESOURCE_BUCKET)
    blob = bucket.blob(GCS_BLOB_PATH)
    
    # 만약 기본 버킷명으로 찾을 수 없다면 배포된 adc-demo 버킷 자동 탐색
    if not blob.exists():
        for b in storage_client.list_buckets():
            if b.name.startswith("adc-demo-"):
                cand = b.blob(GCS_BLOB_PATH)
                if cand.exists():
                    bucket = b
                    blob = cand
                    break
                    
    if blob.exists():
        glossary_data = json.loads(blob.download_as_text())
        print(f"  GCS로부터 데이터 로드 완료 ({bucket.name}/{GCS_BLOB_PATH}).")
    else:
        raise FileNotFoundError(f"로컬 및 GCS 모두에서 비즈니스 용어집 파일을 찾을 수 없습니다. 인프라 배포 상태를 확인하세요.")

print(f"총 {len(glossary_data)}개의 비즈니스 용어 정의가 준비되었습니다.")

# %% [markdown]
# ## Step 6: 비즈니스 카테고리 및 용어 생성

# %%
# 5. 계층 구조에 따른 카테고리 및 용어 생성
glossary_parent = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}"
)

# 기존에 등록된 모든 용어 리스트를 조회하여 세트에 저장
existing_terms = set()
list_terms = subprocess.run(
    [
        "gcloud",
        "dataplex",
        "glossaries",
        "terms",
        "list",
        f"--glossary={GLOSSARY_ID}",
        f"--location={LOCATION}",
        f"--project={PROJECT_ID}",
        "--format=value(name)",
    ],
    capture_output=True,
    text=True,
)

if list_terms.returncode == 0 and list_terms.stdout.strip():
    for term_path in list_terms.stdout.strip().split("\n"):
        term_id = term_path.split("/")[-1]
        existing_terms.add(term_id)
print(f"기존 등록 용어 조회 완료 (기존 용어: {len(existing_terms)}개)")

# ----------------------------------------------------
# 모든 카테고리, 메인 용어 및 동의어 생성
# ----------------------------------------------------
print("\n--- 모든 카테고리 및 용어 생성 시작 ---")
new_terms_created = False

for entry in glossary_data:
    cat_id = entry["category_id"]
    cat_name = entry["category"]
    cat_path = get_or_create_category(cat_id, cat_name, glossary_parent)

    sub_cat_id = entry["sub_category_id"]
    sub_cat_name = entry["sub_category"]
    sub_cat_path = get_or_create_category(sub_cat_id, sub_cat_name, cat_path)

    term_name = entry["term"]
    term_id = entry["term_id"]
    description = entry.get("description", "")
    synonyms = entry.get("synonyms", [])

    # 1. 메인 용어 생성
    if term_id not in existing_terms:
        print(
            f"메인 용어 등록 중 (REST API): {term_id} ({term_name}) under {sub_cat_id}..."
        )
        if create_glossary_term(term_id, term_name, description, sub_cat_path):
            existing_terms.add(term_id)
            new_terms_created = True

    # 2. 동의어 생성
    for idx, syn_name in enumerate(synonyms):
        syn_term_id = f"syn-{term_id}-{idx+1}"
        if syn_term_id not in existing_terms:
            syn_desc = f"[{term_name}의 동의어] {description}"
            print(
                f"  └─ 동의어 등록 중 (REST API): {syn_term_id} ({syn_name})..."
            )
            if create_glossary_term(
                syn_term_id, syn_name, syn_desc, sub_cat_path
            ):
                existing_terms.add(syn_term_id)
                new_terms_created = True

# 새롭게 생성된 용어가 있는 경우에만 인덱싱 대기를 위해 일시 대기
if new_terms_created:
    print(
        "\n신규 용어가 생성되었습니다. Knowledge Catalog 검색 인덱싱 반영을 위해 15초간 대기합니다..."
    )
    time.sleep(15)
else:
    print("\n새로 생성된 용어가 없어 대기 없이 즉시 진행합니다.")

# %% [markdown]
# ## Step 7: 리소스 연동 수립

# %%
# 안정적인 연동 수립을 위해 진입 전 대기
print(
    "\n용어 생성 완료. 관계 링크 수립(EntryLinks) 단계로 진입 전 10초간 대기합니다..."
)
time.sleep(10)

print("\n--- [비즈니스 용어 관계 및 리소스 연동 수립] ---")
processed_links = set()

for entry in glossary_data:
    term_id = entry["term_id"]
    term_name = entry["term"]
    term_entry_path = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entries/projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{term_id}"

    # A. 물리 테이블 연동 (Definition Link)
    related_tables = entry.get("related_tables", [])
    for table in related_tables:
        dataset_name, table_name = table.split(".")
        bq_entry_path = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{dataset_name}/tables/{table_name}"

        base_link_id = (
            f"lk-{term_id}-to-{dataset_name}-{table_name}".lower().replace(
                "_", "-"
            )
        )
        link_id = base_link_id[:63].rstrip("-")

        print(f"  └─ 테이블 매핑 진행: {table} ...")
        if link_term_to_table(term_entry_path, bq_entry_path, link_id):
            print(f"     [성공] 테이블 연동 완료 ({link_id})")

        synonyms = entry.get("synonyms", [])
        for idx, syn_name in enumerate(synonyms):
            syn_term_id = f"syn-{term_id}-{idx+1}"
            syn_entry_path = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entries/projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{syn_term_id}"

            syn_link_id = f"lk-{syn_term_id}-to-{dataset_name}-{table_name}".lower().replace(
                "_", "-"
            )
            syn_link_id = syn_link_id[:63].rstrip("-")

            print(
                f"  └─ [동의어 매핑] {syn_name} ({syn_term_id}) <-> {table} ..."
            )
            if link_term_to_table(syn_entry_path, bq_entry_path, syn_link_id):
                print(f"     [성공] 동의어 테이블 연동 완료 ({syn_link_id})")

    # B. 연관 용어 상호 연동 (Related Link)
    related_terms = entry.get("related_terms", [])
    for rel_id in related_terms:
        sorted_ids = sorted([term_id, rel_id])
        link_key = tuple(sorted_ids)
        if link_key in processed_links:
            continue

        rel_entry_path = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entries/projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{rel_id}"
        base_link_id = (
            f"lk-rel-{sorted_ids[0]}-to-{sorted_ids[1]}".lower().replace(
                "_", "-"
            )
        )
        link_id = base_link_id[:63].rstrip("-")

        print(f"  └─ 연관 용어 상호 연동 진행: {term_id} <-> {rel_id} ...")
        if link_related_terms(term_entry_path, rel_entry_path, link_id):
            print(f"     [성공] 연관 용어 링크 완료 ({link_id})")
        processed_links.add(link_key)

    # C. 동의어 상호 연동 (Synonym Link)
    synonyms = entry.get("synonyms", [])
    for idx, syn_name in enumerate(synonyms):
        syn_term_id = f"syn-{term_id}-{idx+1}"
        syn_entry_path = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entries/projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{syn_term_id}"

        sorted_ids = sorted([term_id, syn_term_id])
        link_key = tuple(sorted_ids)
        if link_key in processed_links:
            continue

        base_link_id = (
            f"lk-syn-{sorted_ids[0]}-to-{sorted_ids[1]}".lower().replace(
                "_", "-"
            )
        )
        link_id = base_link_id[:63].rstrip("-")

        print(f"  └─ 동의어 상호 연동 진행: {term_name} <-> {syn_name} ...")
        if link_synonym_terms(term_entry_path, syn_entry_path, link_id):
            print(f"     [성공] 동의어 링크 완료 ({link_id})")
        processed_links.add(link_key)

# D. 커스텀 Aspect Type 생성 및 SQL Mapping Aspect 첨부
print("\n--- [커스텀 Aspect Type 생성 및 용어 Aspect 첨부] ---")
if not create_sql_mapping_aspect_type():
    print("  [경고] Aspect Type 생성 실패로 인해 Aspect 첨부를 건너뜁니다.")
else:
    print("  Aspect Type 등록 확인 완료. 인덱싱 대기 (3초)...")
    time.sleep(3)

    for entry in glossary_data:
        term_id = entry["term_id"]
        sql_map = entry.get("sql_mapping")
        if sql_map:
            term_entry_path = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/entryGroups/@dataplex/entries/projects/{PROJECT_NUMBER}/locations/{LOCATION}/glossaries/{GLOSSARY_ID}/terms/{term_id}"
            print(f"  └─ sql-mapping Aspect 첨부 진행: {term_id} ...")
            if attach_aspect_to_term(term_entry_path, sql_map):
                print(f"     [성공] Aspect 첨부 완료 ({term_id})")

print(
    "\n전체 비즈니스 용어 계층 구조, 메타데이터, 리소스 연동이 Knowledge Catalog에 성공적으로 등록되었습니다!"
)

# %% [markdown]
# ## Step 8: Knowledge Catalog 용어집 등록 결과 조회 및 검증

# %%
print("--- [등록된 카테고리 목록] ---")
# !gcloud dataplex glossaries categories list --glossary={GLOSSARY_ID} --location={LOCATION} --format="table(displayName, name)"

print("\n--- [등록된 용어 목록] ---")
# !gcloud dataplex glossaries terms list --glossary={GLOSSARY_ID} --location={LOCATION} --format="table(displayName, description, parent)"

# %% [markdown]
# ## Step 9: 대화형 분석 에이전트 생성 및 거버넌스 효과 실습
#
# 지금까지 Data Profile, Data Quality, Table/Dataset Insight, 비즈니스 용어집(Business Glossary) 및 SQL 매핑 규칙을 지닌 Aspect 구축을 마쳤습니다. 이제 이 거버넌스 메타데이터들을 소스로 삼아 작동하는 **대화형 분석 에이전트**를 생성하고 자연어 질의 성능을 테스트합니다.
#
# ---
#
# ### 1. Knowledge Catalog에서 비즈니스 용어집 확인
# 1. Google Cloud Console 상단 검색창에 **Knowledge Catalog**를 입력하여 서비스로 이동합니다.
# 2. 좌측 탐색 메뉴에서 **Glossaries(용어집)**를 선택하고 **TheLook Glossary**를 클릭합니다.
# 3. **고객 분석(Customer Analytics)** 카테고리 하위의 **고객 행동(Customer Behavior)** 하위 카테고리에서 **VIP 고객(VIP Customer)** 용어를 클릭하여 확인합니다:
#    - **동의어(Synonyms)**: `우수 고객`, `핵심 고객`, `고가치 고객`, `High Value Customer`, `VIP`
#    - **설명(Description)**: `누적 주문 총액이 500달러 이상이거나 주문 건수가 5회 이상인 우수 고객군`
#    - **Aspects (`SQL Mapping Ruleset`)**:
#      - **Mapping Type**: `SQL_Filter`
#      - **SQL Filter Condition**:
#        ```sql
#        id IN (
#          SELECT user_id
#          FROM thelook_ecommerce.order_items
#          GROUP BY user_id
#          HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5
#        )
#        ```
#      - **Associated Table**: `thelook_ecommerce.users`
#
# ---
#
# ### 2. BigQuery Studio에서 에이전트 생성 및 데이터 소스 연동
# 1. Google Cloud Console의 BigQuery Studio 화면으로 이동합니다.
# 2. 탐색기(Explorer) 패널에서 **에이전트(Agents)** 탭을 선택하고 **`+ New agent` (새 에이전트)**를 클릭합니다.
# 3. Agent Editor 화면에서 다음을 설정합니다:
#    - **Agent name**: `test agent` 입력
#    - **Knowledge sources**: 파란색 **`Add source`** 버튼 클릭
#    - "Add knowledge source" 창의 검색창에 현재 프로젝트 ID를 입력하여 `thelook_ecommerce` 데이터셋의 테이블 목록을 검색합니다.
#    - 7개 테이블(`users`, `products`, `orders`, `order_items`, `events`, `inventory_items`, `distribution_centers`)을 모두 체크박스로 선택하고 하단의 **`Add`** 버튼을 클릭합니다.
#
# ---
#
# ### 3. 자연어 질의 테스트 및 에이전트 응답 분석
# 에이전트 우측의 **Preview(미리보기)** 테스트 패널에 다음 자연어 질문을 입력합니다:
#
# > **질문:** `"지난 달에 주문 이력이 존재하는 우수 고객은 총 몇 명인가요?"`
#
# #### 에이전트의 응답 결과:
# - **동의어 및 Aspect 규칙 해석**: 에이전트는 Knowledge Catalog 비즈니스 용어집을 조회하여 '우수 고객'이 **'VIP 고객(VIP Customer)'**의 동의어임을 식별하고, Aspect에 정의된 다음 SQL 매핑 조건을 자동 추출합니다:
#   ```sql
#   id IN (
#     SELECT user_id
#     FROM thelook_ecommerce.order_items
#     GROUP BY user_id
#     HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5
#   )
#   ```
# - **자동 생성된 SQL 쿼리**:
#   ```sql
#   WITH VIP_Users AS (
#     SELECT user_id
#     FROM `thelook_ecommerce.order_items`
#     GROUP BY user_id
#     HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5
#   ),
#   last_month_orders AS (
#     SELECT DISTINCT user_id
#     FROM `thelook_ecommerce.orders`
#     WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
#   )
#   SELECT COUNT(DISTINCT v.user_id) AS vip_user_count
#   FROM VIP_Users v
#   JOIN last_month_orders l ON v.user_id = l.user_id;
#   ```
# - **최종 집계 결과**: VIP 고객 수(예: `vip_user_count: 229`)와 함께 비즈니스 요약 답변을 반환합니다. 쿼리 내 `CURRENT_TIMESTAMP()` 함수가 실행 시점을 기준으로 최근 30일 주문을 필터링하므로, 실습 실행 시점에 따라 반환되는 정확한 수치는 달라질 수 있습니다.
#
# ---
#
# ### 4. 거버넌스 메타데이터(용어집/Aspect)의 중요성 비교
#
# 만약 비즈니스 용어집이 등록되어 있지 않다면, 에이전트는 다음과 같이 오답을 내거나 사용자에게 기준을 반문합니다:
# > *"우수 고객을 파악하기 위해 thelook_ecommerce 데이터셋의 users, orders, order_items 테이블을 확인했습니다. 다만 스키마 내에 **'우수 고객'**을 분류하는 구체적인 수치적 기준이 명시되어 있지 않습니다. 어떤 기준으로 정의하면 좋을지 알려주세요..."*
#
# ![거버넌스 메타데이터 중요성 비교 흐름도](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABiAAAAUoCAIAAACqxooqAAAQAElEQVR4nOzdB3hUVcLw8ZuQ0DuoVKWLiqCiiBX72tfXtWDBLgJKU0ERFEURFBUQVBB0Lbi6a1nfXdsqtrWiiFJUVBSkg3RCD/BdnP3ystQkM5NM+f2eeXgOMzeETCZl/nPOuVmbN28OAAAAAKCwMgMAAAAAiILABAAAAEBUBCYAAAAAoiIwAQAAABAVgQkAAACAqAhMAAAAAERFYAIAAAAgKgITAAAAAFERmAAAAACIisAEAAAAQFQEJgAAAACiIjABAAAAEBWBCQAAAICoZAUAxNr341Ysmrs+AAASWFbJjCPOqBYAEAsCE0DsTf9u1S+TVgUAQAIrVTZTYAKIFYEJIF72P6pKxeolAwAg8Xz+vwsCAGJHYAKIl5oNyu65T5kAAEg8AhNAbNnkGwAAAICoCEwAAAAAREVgAgAAACAqAhMAAAAAURGYAAAAAIiKwAQAAABAVAQmAAAAAKIiMAEAAAAQFYEJAAAAgKgITAAAAABERWACAAAAICoCEwAAAABREZgAAAAAiIrABAAAAEBUBCYAAAAAoiIwAQAAABAVgQkAAACAqAhMAAAAAERFYAIAAAAgKgITAAAAAFERmAAAAACIisAEAAAAQFQEJgAAAACiIjABAAAAEBWBCQAAAICoCEwAAAAAREVgAgAAACAqAhMAAAAAURGYAAAAAIiKwAQAAABAVAQmAAAAAKIiMAEAAAAQFYEJAAAAgKhkBQCQ/MaN+/iHH6aEg//5n4srVKgYFImXXhqzenVOzZp1Tj75zKDgNm/ePG/enJUrl++9d4MyZcrs9vgo312sfPvtxNzcDeXLV2zYsElA/D3++JCffvquUqUqffrcF6SlvK/u8867rGzZspErX3jhz1999VlGRub9948IEsa//z12xoxpJUpkXXLJNUEcRL4J1K6994knnh655tlnH580aXyi3Q8ApCeBCYBEESkX+Tx4r71q1ahRK++vEyZ8/uqrL4SDk08+qxCBaeLEr957741ff/1l5szpJUuWrFu3flhPzj77wlq16uzirV555bnFi39r2bJ1QYvPDz98++STw7//ftK6desi19SsWfvEE8+46KKrsrKyYv7utnHvvb0+/PCd/B9/550PHnFEm7y/9u9/a+S/ce+9w/P5L3zzzZd9+3Zfu3ZtUChNmzYbOvSpoJjMmjXjX//6x8cfvxvWwF0cts8+DY4++oRTTjl764dlTITBYtKkCdWq7RGkkDAP/fnPj+zigKuuuuHCC6+IjPO+us8447y8wBR+XsK7JTMzxpPxw5h1xx3d8n98+Hl//PG/5f31008/eP/9t7Kzs+MUmCLfBA4//Oi8wDRr1vR43A8AUAgCEwCJIlIu8nnwZZd1iMlTuDDxPPbYoDfffDXvmlWrgqVLl0ya9NU///nilVfecN55lwYx9emnH9xzzy0bN27c+sowXowZ8/jkyRPuvntoqVKlgtTy00/fF7ouhaZOnZKbm7uL9BYnOTkrhw7t/+9/j83PwWGdDC/PPTf6T3+69OqrO5coUSJIQhdffFr+vwa3EX7IPXrcdfzxpwax8L//+9e8wJTCRo9++MUXn9nZrWHmHjLkqTB5BwCQDAQmANLakCH3vPfem+EgOzv7wguvbN78kM2bN7/11v++//5bYdQYNWpIuXLlTzvtnCBGfvzxu3vv7RXWpTCXdO7c65BDDq9YsfLMmdOfeOLhb775cuLE8Q89dFevXvcG8XTxxdecccaftr4mLCOPPHJ/ODjyyOPOOaftNsfXq9coiJGuXXvXrl03/8c/+eTwsC4FxSEsj336dPn++8nhOHyGf9ZZ5x90UKsdtr/169cvXDgvjGiRTPnyy2NWr17VrVvvIM2Ej+opU77JZ2AKD9tvvwN3eNOwYQNnzZqxYcP6oDg0bdps+7VmeY/D8GuzSpWqW99UqlTpIG5+/vnHr7/+4vDDjw4AIBkITAAkir/85c1trnnuudHPPLPlyd7gwU/uv3/zINYmTZoQqUu1atXp129I3br1ItcfdNBhxx13SliCwsoQpp/wyXDp0qVzclb+/PMPW795/hf05Rkx4sENG7a81e23D2rd+pjIlU2a7Ne//7Bbb+04efLXH3zw9h//2DYeH2yeevUabnNNdvZ/pkhUrVq9RYtDg7hp3Hi/xo2b5v/4SpUqB7E2e/bMq68+NxyE6fCVVz7Y2WFPP/1YpC6Fd8jNN9+55541gt0566wL7rzzxoUL57/55t/DKLD1usJk0bv3wEI8qpcuXTJgwG0FepO99qoZXnZ4U/h5CaL2xht/Hzq0f/B7M+3b94H8v2H4kNv+SyDvcRh+YebnkZB/p59+7mGHHbn99Z999uHf//58OCiu0AYAhSAwAZC+Xn55TGTQq9eAvLoU0br1sRdddPVTTz26cuWKd97551lnnT99+rSePTsEUZg3b863304MBy1bts6rSxFZWVnt23fv3PmycDx27OtxDUzsVhgWX3/95XBQu3bdsP1lZ2fn560aNmxy991Db7jh0rAhvvbaSzEJTOGjbtq0qeFgyZJFX331efjICeLpgANaBAUXNrWAQgnT9g43eps1a0YAAMnGjoAApKm1a9eOH/9pONh33wOaNNlv+wNOOeXsyOCLLz4JYuHrr7+IDE4++aztb23SZP/IedkmT54QFK1ly5ZEBkpBxOzZv65duyb4fYJJPutSRL16DQ844KBwEJn9FKVXX32hc+d2y5cvC34/5+Btt93w8MMD8jaGT1WbNm0K/0yoXavzdkwLPwsBALATZjABkKbCqpKbmxsOmjU7aIcHVKtWvW7derNmzZg9e0b41wMPPPhf/xq/9QEF3RF5zpyZkUHNmrV3eEDNmnV+/vnHmTOnh89jMzIygiIxffq0yAZMwZaU9vGoUUOvuaZLkb33xLRu3X+2JK9UqUpQQHvvXf+bb75ctSpnw4YNBYpTW1u5csWDD9712WcfhuPwc3HBBZe//fY/li5d8vrrL0+a9NWtt/Zv1GjfIEUtWrQw2LJQrsL2N118cWx2EC+QuXNnT5nydWT8wQf/KuKtx+++u2cAAEnCDCYA0lTe5iYlSuz05ZbKlbf0hSVLFgexEJkUE9pjjx1v45K3vUvkOXYR+Pzzf3frdkXk3TVqtGV3pJdeerZfvx7RnPRte2XK/OfU8u+++3pQ3KpV2yOSz7ZZFLm1ihX/s+dOIT4RYR8Mft8zvtB16bvvJnXseFGkLu2xx14PPfTEVVfdMHLk3w499Ijg98VT4afs5ZefC1JR+LEvWbIo2PJojKqghZ/lyKB27b2DKCxcOP/WWzvmfTk8+eTwV199IQAAdsQMJgDS1n8m6eStf9leZEVMrFbr5L2jnZ3DvmTJ/5ykrGiWQf31r0+FT5iD3+fI3HjjHSeeePqjjw567bWXPv30gxtvvOquuwaHdSOIhYMOahXeh5s2bfr7359ftmzpDjed2aHZs38NYq1MmTJhdAj/5Tp19tnZMTVr1q5UqfLy5cveeeef559/WVZWfn9fmj592nffbdlmq2nTZkHB5ebmPv/8E889NzrywDvmmBO7detTvvyWuTzh/6d//2H/+MffHn988IYNG8I/v/zyky5dbsv/nZn4wsfGQw/1i4x3uIy0d++Beftth4/er776fGf/VKSWhnbxWd6t+fPn3nJLhwUL5gW/nwDxgw/+NXHi+MceeyBMYGHyC4rEZZd12HqKZf/+t0aWTAJAAhKYAEhTkeftoZycFTs7JnzGG8TnXGbFa/XqVffdd/vnn/87+H160e233x/ZPbpz51vr12/0yCP3//zzj9ddd2H79t1PPfWPQdTq1Nm7T5/77r23VxhQ3n//rSDWvvtuUvfuVwW/TwF79tnXdnt8w4ZNwsC0ixlMYQE888zzwtAzZ86s22/v2qNHv6pVqwW7E95pfft2X79+y8y4s866ICigWbNmhHfRL7/8FI5Lly593XU3nX76/2xzzNlnX3DwwYf3739LWLK+/vqL6667oG3bqy688Ir8J7CEFX5E4V39228LwvEll1yzw3OrHXDAQdWqVY+M3377n7v418LDqlSpunTpkr33rh8USvip79nzusgUti5deoWfixNOOK137xumTPkmbFtr167p1KlHEH/h1+PWZ7XLyirktDgAKAICEwApZerUyQsXzouMS5UqvYuJJOHzz7Ax5eSsDPPEDg8In51GZtBEnqNOnvz1zTdfGyS/adN+6Nfv5si8jOrV9+zXb0hkc/GIMKzstVethx66a8mSxYMH3/3JJ+9169Ynb8FRoR111PH9+w+7774+hVhvGN7/sQ0oLVseEX5ymzU7eBfHXHTR1RMnjg9rwoQJ46688pyzzjo/fJ5fsmTJ7Y8Mi9KCBXN/+OHbvOQRVrk2bU4O8m3z5s0vvvjM008/FtkU7MADD+7atffO+lfduvsMHz7mpZeeff75J9auXfvMMyPCZtely23Nmx8SJK133nlt+PCBkZVo111347nnXhxErU2bU8JaV79+46DgfvppatiSInOFwvv2jDPODX6vfnff/fDtt3cJHxX/+79/XbNm9Y033hGn3coij4QgwTY7B4BdE5gASCkDB/bJG++zT4PHH//bLg4++OBWH3307qxZMz799IMjjzxum1ufe27U/z/s8KBoXX31uUHchM/kI3XptNPOufbabuXKld/mgMMOO3LkyL+NGPHgu+++EeaVMAlFH5iCLQvlDnv++X8FCeAPfzg7vOz6mOzs7DC9Pfzw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/pE333ztr7/+8uOP34VPZYO4CUPVDz9MCWKkVq26+dkmvEKFivfcMyxsTDk5K5csWfzwwwN2ffzgwU/uv3/zoODCvDJnzswgRpo0OSCaM4JVqLAlLoStYeHC+QXqL2FUisx/KVOmbD7rUqhs2XIDBz7au3fnBQvm/fzzj+El76YSJUpcdNHVZ555XkChTJ/+04YN68NBly63NWjQeBdHHnfcKTNn/vLcc6P32695QZfgJSN1CYC4EpgAiLvUa0wVK1Z66KEnbr+9a9gjfvnlp50dVrJkySA6CxfO69mzQxAjHTvenM9NgmrXrtuv35DRo4d+992kIG4+//zfkVPIx8SIES/UhguheAAAEABJREFUr98oKKyWLVtH1rjddtsN117brVWro/JTi2bOnP7MMyN++un74PepbUFB1K1b789/fjW8E95557XwX8jJWVG/fuMjjmhz0klnVqtWPYi1MGlFBtOmTS1QQUs6Rx553GOPvfDxx++ecspZuz34sss67Ltvs3TYg0ldAiDeBCYAikLqNaby5SsMHvxkkLoOOKBFan+A2wirxDHHnPjRR+/OmjWjELPSqlXb45prugQFVKJEiaOOOj68BPHXsuURTz316IYNGwYMuK1z51577VUzn28Yp7PILVu2JHKKt3j8N8JCeuGFV+TzYHUJAGJCYAKgiKTweeXiZ++96//rXwV4Ep5czjzzvIRaCHbrrf3r12/80kvPrl69qkBveOyxJ119dZf8LD8sRvXrN7rttgH33HPL+vXrH3zwrqC4ff31F+ElIP7UJQCKhsAEQNHZtjFdWCsz/U5neuSRx9WqVadEidT8EVy3br3mzQ9J0u1ssrKyLrnkmj/96dIC7Xu15541a9asHRShc8+9ZPXqnJo16wQFFD72+vS574EH7ly1KqdAb5iRkdGixaFBLFSqVLlJk/1//PG7oOBi+N/YhfCODR/DwZYlrqWC5KcuAVBkMjZvTpGTRgOQLFYs3hA2pjU5G2s3Lnf0+TXTsDEBFIGJ7y3+7tOl6hIARcMv9QAUtcg8pjLlS8z5adXHL87btCkAILbUJQCKmMAEQDHQmADiR10CoOgJTAAUD40JIB7UJQCKhcAEQLHRmABiS10CoLgITAAUJ40JIFbUJQCKkcAEQDHTmACipy4BULwEJgCKn8YEEA11CYBiJzABkBA0JoDCUZcA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3HPP7dGjR3Z2dj7f1jwmCPJdl7b28ssvDxo0KDc399hjj+3fv3+ZMmUCACA+BCYAiLucnJyePXt+8cUXYVTq27fvqaeeGhSQxkSaK0Rdipg6dWr37t1/++23unXrDh06dO+99w4AgDgQmAAgvqZNm9atW7f58+fXqFFjyJAhjRo1CgpFYyJtRepSiayMczoWrC5FLF++vEePHhMmTChdunT//v3btGkTAACxZg8mAIijt956q2vXritWrGjVqtXIkSPDxhQUlv2YSE95dems9rVqNyrMGrewK51xxhkbNmwYP37822+/nZOTE349Zmb6+gGAWDKDCQDiInw2++CDD7700ksZGRnX/i4cBFEzj4m0snVdqtM42h2UPvnkk169eq1evbp58+bhl2eVKlUCACBGBCYAiL2FCxd27979hx9+KF++/H333Xf44YcHsaMxkSZiW5ci5syZ07Vr1xkzZlSrVi1sTM2aNQsAgFiwRA4AYuyrr7667rrr5s6d26hRo9GjRzdt2jSIKWvlSAfxqEuhihUrnn322b/++uu333772muvlStX7sADDwwAgKgJTAAQS08//XTfvn3Xrl176qmnDhkypFKlSkEcaEyktjjVpYisrKyTTz45LE2ff/75J5988vPPPx9zzDHhlQEAEAVL5AAgNlatWtWrV69PP/00Ozu7R48e5557bhBn1sqRkuJal7Y2ZcqUm266afHixfXq1Rs6dGjt2rUDAKCwBCYAiIGZM2d27dp11qxZe+yxx+DBg2O+LG5nNCZSTJHVpYilS5eGjWnSpElly5YdMGDAUUcdFQAAhWKJHABE68MPP7z++uuXLFlyyCGHPP7443Xq1AmKirVypJIirkuhMmXKnHnmmatXr54wYcJbb721fv36Qw89NCYnfASAdGMGEwAU3saNG4cMGfL888+H4yuuuKJTp06ZmcUQeMxjIgUUfV3aWpiJe/fuvXbt2jATDxo0KE67pwFAChOYAKCQEmpxjcZEUvvy9YXTvl5RXHUporgWugJAajCNHgAKY8qUKW3btg3rUr169Z5//vli37qlYtWsP3WpU65S1vzpaz58Yc6mjQEki0SoS6G99977L3/5y7HHHvvbb79dccUVL7/8cgAA5Js9mACgwMJnobfddtuqVatOPPHEYcOGVa1aNUgA9mMiGSVIXYrIzs7+wx/+ULp06XHjxn300UczZ848+uijS5QwIRAAds8SOQAogLVr1/bt2/fdd9/Nysrq1q1b27ZtgwRjrRxJJKHq0tYmTpx40003LVu2rFGjRkOGDKlRo0YAAOySwAQA+TVnzpyuXbvOmDGjWrVqDz74YLNmzYKEpDGRFBK2LkUsWrQobEzffvtt+fLl77vvvsMPPzwAAHbOEjkAyJdPPvmkY8eOv/32W/PmzUeNGrXPPvsEicpaORJfgtelUNmyZc8666xly5Z98803b7zxRviibMuWLTMyMgIAYEfMYAKA3di0adMjjzzy9NNPh+NLL720c+fOSbEni3lMJKzEr0tbGzt2bN++fdetW9eqVav777+/fPnyAQCwHYEJAHZl+fLlPXr0mDBhQunSpfv379+mTZsgeWhMJKDkqksR06dP79q169y5c2vUqDFkyJBGjRoFAMB/M2MeAHZq6tSpbdu2DetS3bp1//KXvyRXXQpVrJr1py51ylXKmj99zYcvzNm0MYDilYx1KVS/fv3nn3/+yCOPnD9/frt27d56660AAPhv9mACgB176aWXevbsmZOTc+yxxz766KPVq1cPkpD9mEgcSVqXIkqWLHnaaadlZmZ++eWX77333qJFi1q3bp0Uq2UBoGhYIgcA21q/fn2/fv3eeuut8NnjDTfc0K5duyDJWStHsUvqurS1cePG3XLLLWF63nfffQcPHrznnnsGAIDABADbmD9/frdu3aZNm1a5cuUHH3ywRYsWQUrQmChGKVOXIvK+S1SsWHHQoEEtW7YMACDtWSIHAP9n3LhxHTp0CJ89HnDAAaNGjWrQoEGQKqyVo7ikWF0KlS9f/uyzz54zZ8633377xhtvZGVlHXzwwQEApDczmABgi/AH4siRI0ePHh2OL7jgghtvvDF80hikHPOYKGKpV5e29uqrr953330bNmw48sgjBwwYUK5cuQAA0pXABABBTk7Orbfe+vnnn5csWfKOO+449dRTg9SlMVFkUrsuRXz//ffdu3dftGhRzZo1B6aAIb8AABAASURBVA8e3KhRowAA0pLABEC6mzZtWrdu3ebPn1+rVq2hQ4fWr18/SHUaE0UgHepSxPLly3v06DFhwoRSpUr17dv3lFNOCQAg/diDCYC09tZbb3Xt2nXFihVHHnnkY489liYnhLIfE/GWPnUpVLp06TPPPDN81fbLL7989913w+8nrVq1ysz0RQVAejGDCYA0tWHDhkGDBr3yyisZGRnXXXfdNddcE6QZ85iIk7SqS1v77LPPbr311lWrVjVr1mzw4MFVqlQJACBtCEwApKOFCxd27979hx9+KF++/H333Xf44YcHaUljIubSti5FzJ49+8Ybb/zll1+qV68eJuwDDzwwAID0YIkcAGnnq6++uu666+bOnduoUaPRo0c3bdo0SFfWyhFbaV6XQhUrVjzrrLNmzZo1ZcqU119/vUKFCs2aNQsAIA0ITACkl6eeeir82bd27dpTTz11yJAhlSpVCtKbxkSsqEsRWVlZJ510UliaPv/8848//nj69OlHH310eGUAACnNEjkA0sWaNWtuueWWTz/9NDs7u0ePHueee27A/2etHFFSl7Y3efLk7t27L1u2rEGDBkOHDq1Zs2YAAKlLYAIgLcycObNr166zZs3aY489Bg8enM7L4nZGY6LQ1KWdWbRo0c033zxlypTy5csPGDDgiCOOCAAgRVkiB0Dq+/DDD6+//volS5Yccsghjz/+eJ06dQK2Y60chaMu7ULZsmXPPPPMnJycCRMmvPnmm+E14XehjIyMAABSjhlMAKSyjRs3Dh069C9/+Us4vuKKKzp16pSZqZrsinlMFIi6lE9vv/32XXfdtW7dutatWw8YMKBChQoBAKQWgQmAlLV06dKbbrpp0qRJZcuWDZ/RHXXUUQH5oDGRT+pSgfz888/hd6TZs2fXqFHjoYceatKkSQAAKcSruACkpilTprRt2zasS/Xq1Xv++efVpfyrWDXrT13qlKuUNX/6mg9fmLNpYwDbU5cKqmHDhmPGjGnduvX8+fMvv/zyt99+OwCAFGIPJgBS0AsvvHDbbbetWrXqxBNPHDZsWNWqVQMKwn5M7Jq6VDglS5Y87bTTSpQo8eWXX7777rvLli07/PDDrdsFIDVYIgdASlm/fv3tt98ePnMLn8J17dr14osvDigsa+XYIXUpep999lmvXr1ycnKaNWv2wAMPVK9ePQCAJCcwAZA65s+f361bt2nTplWuXPnBBx9s0aJFQHQ0JrahLsXKvHnzbrzxxp9++in8fjV48OADDzwwAIBkZokcACniq6++at++fdiYDjjggFGjRjVo0CAgatbKsTV1KYYqVKhw9tlnz5w587vvvnv99dfDzLT//vsHAJC0zGACIBU8+eSTjz32WPhD7dxzz+3Zs2dWVlZA7JjHRKAuxc0LL7wwePDgjRs3nn766X369ClZsmQAAElIYAIgua1Zs+aWW2759NNPs7Oz+/bte+qppwbEgcaU5tSluPr6669vvvnm5cuXN27ceMiQIXvttVcAAMlGYAIgic2cObNr166zZs3aY489hg0b1qhRo4C40ZjSlrpUBBYsWHDTTTdNnTq1UqVKAwcOPOywwwIASCr2YAIgWX3yyScdO3ZcsmTJIYcc8vjjj9eqVSsgnuzHlJ7UpaJRvnz5s846a968eVOmTHnzzTdLlSrlNAUAJBczmABIPps2bXr00UefeuqpcHzppZd26dIlM1PqKCLmMaUVdanovfTSSw888EBubu7xxx/fr1+/MmXc7QAkB4EJgCSTk5Nz4403TpgwoXTp0v3792/Tpk1A0dKY0oS6VFwmT57cvXv3ZcuW7bPPPkOHDq1Tp04AAAlPYAIgmUybNq1bt27z58+vVavW8OHD995774DioDGlPHWpeC1atOjmm2+eMmVKuXLl7rnnnmOOOSYAgMRmDyYAksbYsWM7d+68YsWKI4888rHHHttjjz0Cion9mFKbulTsypYte+aZZy5btmzixIn/+te/wpeEW7ZsmZGREQBAojKDCYAkkJub+9BDD/3tb38Ln19de+217du3D0gA5jGlJHUpobz++ut33313+D2wdevWAwYMqFChQgAACUlgAiDRLV26tHv37lOmTClfvvx99913+OGHByQMjSnFqEsJ6Pvvvw+/By5atKhGjRq9e/c+4ogjAgBIPJbIAZDQwmdW11577YwZMxo0aDB69OimTZsGJBJr5VKJupSY9thjj9NPPz2M7NOmTXvzzTczMjJatmwZAECCEZgASFyvvPJKz549c3Jyjj/++GHDhlWpUiUg8WhMqUFdSmRlypQ544wzwm+GYXP/8ssvv/vuuzZt2mRnZwcAkDAskQMgEW3YsOHuu+9+4403MjMzb7jhhssuuywgsVkrl9TUpWQxefLk7t27L1u2bJ999hk6dGidOnUCAEgMAhMACWfRokXdunWbOnVqpUqVBg4ceNhhhwUkA40pSalLySXvO2S5cuXC75C2ZAIgQVgiB0BiCV+fv/baa2fPnt24ceNRo0Y1adIkIElYK5eM1KWkU7Zs2bPOOmvevHnffffdm2++mZmZecghhwQAUNzMYAIggbzwwguDBw/euHHjySeffNddd5UsWTIg2ZjHlETUpaT297///b777svNzT366KMHDBhQpozPIADFSWACICGsX7++b9++77zzTlZWVrdu3dq2bRuQtDSmpKAupQBbMgGQOAQmAIrfggULwqj0008/Va5cefDgwQceeGBAktOYEpy6lDJsyQRAgrAHEwDF7Msvv+zYsePcuXObNm06evTo+vXrByQ/+zElMnUpldiSCYAEYQYTAMXpmWeeGT58+KZNm84555xbbrklOzs7IIWYx5SA1KVUZUsmAIqXwARA8Vi7du3tt9/+/vvvZ2VlhYMzzjgjIBVpTAlFXUpttmQCoBgJTAAUg3nz5nXt2vWXX36pXr364MGD99tvv4DUpTElCHUpHdiSCYDiYg8mAIral19+ed111y1YsKBZs2ajRo2qW7duQEqzH1MiUJfSxDZbMpUoUcKWTAAUDTOYAChSTz311COPPBL+9DnvvPNuvvnmrKysgPRgHlMxUpfS0CuvvHL//ffn5ua2adOmf//+pUuXDgAgngQmAIqITZfQmIqFupS2Jk6cGHb8pUuXNmzYcPDgwbVq1QoAIG4EJgCKgk2XiNCYipi6lOZ+++23bt26/fDDDxUqVHjggQdatmwZAEB82IMJgLiz6RJ57MdUlNQlypUrd+aZZ86cOXPq1KlvvvlmxYoVw+/DAQDEgcAEQHw988wz4c+adevW/elPf7rvvvvCZzsB6U1jKhrqEhFZWVknnXRSmTJlPv/8808++WTevHlHHXVUiRJmDwIQY5bIARAvNl1iF6yViyt1ie2NGzeuZ8+eq1at2n///YcMGVK1atUAAGJHYAIgLmy6xG5pTHGiLrEzs2bN6ty58+zZs8PvzA8++OABBxwQAECMmJIOQOx9+eWXF110UViXmjVr9vzzz6tL7FDFqll/6lKnXKWs+dPXfPjCnE0bA6KnLrELdevWHTNmzFFHHbVo0aKrr776zTffDAAgRuzBBECMhc9e+vbtu27dunPPPdemS+ya/ZhiS11it0qWLHnqqafm5uZOmDDh/fffz8nJadWqVWamLzwAomWJHAAxs379+jAtvfPOOzZdokCslYsJdYkCGTt2bPhK89q1aw855JAHHnigYsWKAQBEQWACIDYWLFjQrVu3n376yaZLFILGFCV1iUKYNm1a165dw+/eNWvWHDZsWL169QIAKCyzYQGIgcmTJ1988cVhXWratKlNlygE+zFFQ12icBo1avTcc881b9583rx57dq1+/jjjwMAKCx7MAEQrRdffLFXr15r1qw5/fTTH3roIZsuUTj2YyocdYlolC5d+owzzli2bNmkSZPeeuut7Ozsgw8+OACAgrNEDoDCy83N7dev3xtvvFGiRIlu3bpddNFFAUTHWrkCUZeIlX/84x/9+/ffuHHjSSeddNddd5UqVSoAgIIQmAAopKVLl3bv3n3KlCmVKlV64IEHvOhNrGhM+aQuEVsTJ04MXypYuXLlvvvuO2TIkD322CMAgHwTmAAojB9//LFLly6LFi1q0KDBsGHD9tprrwBiR2PaLXWJeJg7d274vX3GjBlVqlQJG9MBBxwQAED+2NsAgAJ7++23L7/88rAuHX/88c8884y6RMzZ83vX1CXipFatWuF39aOOOmrp0qVXX3312LFjAwDIH5t8A1AAmzZtGjx4cPiy9ubNmzt27HjLLbdkZWUFEAf2/N4ZdYm4ys7OPvXUU3NzcydMmBAGpvXr1x922GEZGRkBAOySJXIA5NfKlSt79Ogxfvz4cuXKDRw48IgjjgggzqyV24a6RJEJ69Idd9wRBqajjjpqwIABZcuWDQBg5wQmAPJlxowZN9xww/z58+vUqTN8+PDwzwCKhMaUR12iiE2dOrVbt26LFi2qV6/eww8/XKtWrQAAdsJccwB276OPPrr00kvDutS6desxY8aoSxQl+zFFqEsUvaZNm/7lL3/Zd999w9cYLrnkkq+++ioAgJ0QmADYjccff7x79+5r16694oorhg0bVr58+QCKlsY0/q3fwroUDs64pqa6RFGqWrXqk08+edJJJ61cubJjx47/+Mc/AgDYEZt8A7BTYVS6+eab//73v5cqVWrAgAEXXnihfV4pLtvs+b33/hUyM9Pl0bhl7tKEFZklgjOvrbVPU/vgUNSysrLCwFSyZMkvvvjiww8/XL58+RFHHOHHAQDbsAcTADu2YMGCzp07//LLL3vuueewYcMaNmwYQHFbsST3lWGzc5bl7rlPmeMuqlUiK/Wf4kZWxoV16Yyra+2zn7pEcfr444979eq1Zs2a1q1b33///bb9BmBrAhMAO/D111/ffPPN4cvUzZo1GzJkSOXKlQNIDHl7fu9Vv8wJl9QOUtqXb/427avl4eCs9uoSCSF81eH666//7bff6tevH772UKNGjQAAfmcPJgC29be//a1Dhw5hXTr99NNHjx6tLpFQIvsxVaiStWD6mnefnbMxN2VfKtsyd+mr5Zkl1CUSSIMGDcaMGdO0adPp06dfeuml33//fQAAvzODCYD/k5ub269fvzfeeKNEiRI33njjhRdeGEBCWrU896Whs1cuTdm1clbGkcjWrVvXp0+f999/v2TJkvfcc88JJ5wQAJD2bPINwH8sW7asU6dOn3zySfny5YcPH37SSScFkKhKls5sfFD5n3/f8/u3WWv3OSCl9vxWl0hwWVlZp5xyyvr167/66qt33nkn/OvBBx8cAJDeBCYAtvj555+vueaa6dOnN2jQYPTo0Y0bNw4gsaVqY1KXSBatWrWqVavWxx9/PG7cuBkzZrRp0yYz0/4bAOnLEjkAgvfee+/2229ft27d0UcfPXDgwNKlSweQJFJsrZy6RNL55ptvunfvvnLwTJH4AAAQAElEQVTlyoMOOuihhx6qWLFiAEBaEpgA0t2jjz765JNPhoNrrrmmQ4cOASSblGlM6hJJavbs2ddff/2cOXNq16798MMP77PPPgEA6UdgAkhfa9eu7d2794cffliqVKmBAwcec8wxASSnFGhM6hJJbcWKFTfeeOM333xTvnz5IUOGHHTQQQEAacYeTABpav78+dddd93XX3+95557jho1ypMBklqy78ekLpHswhcqzj777Llz506ZMuUf//hH+JOladOmAQDpRGACSEcTJ04M69K8efOaN2/++OOP16pVK4Akl7yNSV0iZRx33HHZ2dlffvnlv//97/Xr17dq1SoAIG1YIgeQdsLXlvv3779x48azzjqrd+/eWVlZAaSKpFsrpy6Rej766KNbbrklDEzHH3/8PffcU6pUqQCANCAwAaSRMCo99NBDf/3rXzMzM7t3737RRRcFkHKSqDGpS6Sq77//vnPnzsuWLWvatOnw4cMrV64cAJDqBCaAdJGTk3PjjTdOmDChXLlyYWZq2bJlACkqKRqTukRqmz9/fqdOnWbOnFmjRo1HHnnEqeUAUl5mAEAamDVr1qWXXhrWpTp16owZM0ZdIrWVq5R1Xtc6FapkLfx1zQfPz92Ym3Avp6lLpLywKz3zzDOHHnpoWJouv/zyb775JgAgpdnkGyD1jRs3rmPHjosXL27VqtVjjz22xx57BJDqEnnPb3WJNFGyZMnTTjtt3rx533777RtvvBEmpyZNmgQApCiBCSDFjRkzJvxWv379+rZt29599902WyV9JGZjUpdIK5mZmccff3xYmj7//PMPPvggNzf3sMMOCwBIRfZgAkhZ4e/xYVp66623SpQo0bt377PPPjuA9LNqee7Lw2avWJwQ+zGpS6St9957r0+fPpFTy917773Z2dkBAKlFYAJITStWrOjWrdukSZMqVar00EMPtWjRIoB0tXrlxpeGzir2xqQukebyTi3XrFmzhx9+uGLFigEAKURgAkhBM2bMCH+JnzdvXsOGDYcOHVqjRo0A0luxNyZ1CYKtTi1Xu3btsDE5tRxAKnEWOYBUM27cuHbt2oV16aijjnr66afVJQiVrVDivK51K1YrnvPKqUsQETm13EEHHTRnzpzLL7980qRJAQCpQmACSCnPPfdc586d16xZc+mllw4ZMqR06dIB8LviakzqEmytfPnyI0aMOPXUU3Nycq677rqxY8cGAKQEZ5EDSBG5ubl33333008/nZmZ2a9fv3bt2mVkJMpJ2SFBZJfKbHxwhZ8n5SyZV0TnlVOXYHvhz6kTTjhh06ZN48ePDwNT2bJlmzdvHgCQ5AQmgFSwYsWK66+//qOPPqpQocIjjzxy9NFHB8COFGVjUpdgFw499NC99trr448//uyzz5YsWXLkkUd6XQQgqdnkGyDpzZo1q1OnTvPmzatXr97DDz9cq1atANilItjzW12C/Bg3btxNN920du3aMDANGjSoVKlSAQDJyR5MAMkt/NX80ksvDetSq1atnnnmGXUJ8iPe+zGpS5BPhx9++BNPPFGtWrVPP/30mmuuWbp0aQBAcjKDCSCJjR49esSIEeHgwgsv7NGjRwAURJzmMalLUFALFizo1KnTr7/+WqNGjfDnWp06dQIAko3ABJCsbr/99jfffDMzM7NPnz5nn312ABRczBuTugSFk5OTc+ONN06YMKFixYrDhw/ff//9AwCSisAEkHyWLVvWpUuX7777rkqVKgMHDmzZsmUAFFYMG5O6BNHIzc0NXzIZO3ZsyZIl77333uOOOy4AIHk4ixxAkpkxY8bVV18d/tmwYcMnnniiUaNGARCF2JxXbnPw5RvqEkQlMzPzpJNO2rBhw1dfffX2229XrVrVPCaAJCIwASSTcePGdezYcdmyZUcdddQjjzxSqVKlAIhatI1JXYLYadWq1V577fXRRx99/PHHq1evbt26dQBAMrBEDiBpvPDCCw899NCmTZvatWvXpUuXjIzYn1gd0lkh18ptDj7/x4Lpk1eqSxBDn3zySY8ePdavX3/SSSf179+/RIkSAQCJTWACSAIbN2685557/vnPf4a/Yd95552nnXZaAMRBgRuTugRx8913391www0rVqxo1apV+PpK6dKlAwASmMAEkOjyTqxToUKFIUOGtGjRIgDipgCNSV2COJs9e3b79u0XLlzYpEmTRx55pEqVKgEAiUpgAkho8+fP79Sp08yZM+vUqfPoo4/WqlUrAOIsbEyvDJu97LcNu2pM6hIUiUWLFoU/B3/55ZcaNWqMGjWqZs2aAQAJKTMAIFF9//33l156aViXDjnkkDFjxqhLUDTKVihxXtc6lffIXvjrmg+en7sxd7tX49QlKCrVq1f/85//fOCBB4avuLRr1+6HH34IAEhIAhNAgnrvvfeuvvrqZcuWnXHGGY899lj58uUDoKiULrfzxqQuQdEqV67cyJEj27RpE/5MDH8yfvXVVwEAiWfLZrEBAAnmySefvPfeezdu3HjDDTd07949M9PrAVDUskpmNjmkwi+TVy2eu+63WWv3OaBCZmaGugTFokSJEqeccsrSpUsnTZr01ltv1atXr0GDBgEAiURgAkgsubm5d91111/+8peSJUsOGDDgf/7nfwKgmGzbmPav8MVrC8O6FN505rXqEhSpjIyMo48+Ojs7e9y4cWPHjq1ater+++8fAJAwbPINkEBycnK6dev2zTffVK5cediwYfvtt18AFLc1ORtfGT576YINpcpkrluzKbzmrPbqEhSbN998s2/fvps2bWrXrl3Xrl0DABKDwASQKGbPnt2lS5eZM2fuvffejz76aI0aNQIgMeQ1pkBdggQwbty47t27r1+//pRTTrnnnnssJAdIBAITQEKYMmVK586dV65ceeihhz7wwAO29IZEs3bVxn+Omnf4aVX33lddguIX/ty84YYbcnJyjj766Pvvv79kyZIBAMVKYAIofu+9995tt92Wm5t7xhln3HHHHSVKlAgAgF2aMWNGhw4dFi1a1KJFi+HDh5cpUyYAoPgITADF7Kmnngp/LQ4H119//ZVXXhkAAPkzf/78a6+9dt68efvuu+8jjzxSuXLlAIBiIjABFJuNGzf269fv9ddfz8rKuvfee0844YQAACiIJUuWdOrUadq0aXXq1BkxYoQdDAGKi8AEUDxWr1594403jh8/vkKFCsOGDWvWrFkAABTcqlWrwsb07bffVq9efdSoUXXr1g0AKHJOuABQDBYvXnz55ZeHdal27drPPvusugQAhVauXLmRI0e2bt160aJFV1xxxdSpUwMAipzABFDUfvnll0svvXT69OlhVwrrUp06dQIAIAqlS5ceMmTIKaecsnz58muuuSZ8CScAoGgJTABFKvyV9/LLL//tt9+OP/74UaNGVaxYMQAAopaVldW/f/9zzjln7dq1N9xww0cffRQAUIRK3HnnnQEAReK1117r2bPnhg0bwsbUp0+fEiVKBABAjGRkZBx77LGZmZlffPHF22+/XatWrSZNmgQAFAmbfAMUkUceeeTPf/5z+FvvHXfcceaZZwYAQHy89NJLAwcODAc9evS48MILAwDizwwmgLjbuHFjGJXCX3bLlCkzbNiw4447LgAA4mb//fevW7fu+++//+mnn2ZnZx988MEBAHEmMAHE16pVq7p37/7hhx9Wq1Zt1KhRThgHAEWgcePGDRo0CBvTuHHjVq9e3bp16wCAeLJEDiCOFi1a1KlTp19++WWfffZ59NFH99prrwAAKCqffPLJzTffvGHDhgsuuKBHjx4ZGRkBAPEhMAHEy4wZM8K6tHDhwgMPPHDYsGHly5cPAICi9fXXX99www3r1q0744wz7rzzTo0JIE4yAwDiYNKkSVdccUVYl9q0aTNy5Eh1CQCKxcEHHzxixIhy5cq9/vrrvXv3zs3NDQCIAzOYAGLvgw8+6NWr14YNGy666KIbb7zRi6UAULx++umnDh06LF++/Oijj37ggQeysrICAGJKYAKIsTFjxgwZMiQc3Hrrreedd14AACSAmTNnXn311UuXLj388MMffPDB0qVLBwDEjsAEEEsDBw586aWXsrOzBwwYcNxxxwUAQMKYM2fOddddN3/+/ObNmw8fPrxs2bIBADEiMAHERm5ubp8+fcaOHRv+thr+zhr+5hoAAAlm4cKF1157bViamjVr9uijj2pMALEiMAHEwNq1a7t06TJhwoRq1aqFv602bNgwAAAS0uLFi6+66qpIYwpfE3IiDoCYEJgAorV06dLrr7/+xx9/rFOnzsiRI/faa68AAEhgYWNq3779r7/+2rRp0xEjRmhMANETmACiMm/evGuvvXb+/Pn77bdf+CpopUqVAgAg4S1btuzqq6+ONKZHHnnET3CAKGUGABTWDz/80K5du7AutWrVavTo0X43BYBkUbly5SeeeKJBgwZTp0697rrrli9fHgAQBYEJoJC++uqr8JXP8PXPU089ddiwYaVKlQoAgOQRNqbw9aEmTZpMmzYtbExLly4NACgsS+QACuO999677bbbcnNzr7jiihtuuCEAAJJTTk5O+/btf/zxx3r16o0aNapKlSoBAAUnMAEU2GuvvXbnnXeGgx49elx44YUBAJDMwsbUqVOn7777TmMCKDSBCaBgRo8ePWLEiBIlSvTr1+8Pf/hDAAAkv9WrV3fo0CHSmMIf9NWrVw8AKAiBCSC/wm+YgwYN+tvf/padnT148ODWrVsHAECqCBtTp06dpkyZUrdu3SeffNI8JoACEZgA8mXTpk19+vR5++23y5Yt+/DDDx900EEBAJBawsbUvn37qVOn1qtX74knnnB+WID8E5gAdm/9+vU9e/b8+OOPwxczH3vssUaNGgUAQCrKycm55pprpk2bFv64Hz16dPny5QMA8kFgAtiNVatWdenSZeLEiTVr1hw5cmStWrUCACB1LV++/LrrrgsbU9OmTR9//PGyZcsGAOyOwASwKytXrrz22mvDXzHr168f1qWqVasGAECqCxvT1VdfPWPGjGbNmo0YMaJ06dIBALuUGQCwE0uWLLnqqqsik+SffPJJdQkA0kSlSpVGjRpVr169KVOmdO7ced26dQEAuyQwAezY/Pnzr7jiiunTp4cvXY4ePbpChQoBAJA2qlSpEjamunXrfv311927d9eYAHZNYALYgTlz5oR1ae7cuYcddtiIESNs8AkAaSjSmGrVqvXFF1+EjWnDhg0BADshMAFs65dffgnr0qJFi9q0aTNs2DDbLgBA2qpevfrjjz8e/hk2ph49emzatCkAYEcEJoD/8v3331911VVLly499dRTBw0alJWVFQAAaaxGjRojR46sUqXKxx9/3K9fvwCAHRGYAP7PxIkT27dvn5OTc84559x9992Zmb5JAgDBPvvsE1ky/9prrz3wwAMBANvx3AngP8K61KlTpzVr1lxwwQV9+vTJyMgIAAB+7iPHcAAAEABJREFU17Bh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WBk4cITZEc3IBI7BRERERERxTMKECT08/LZvX//+fbggIiLSIDj4wc8/18iYMQu7XWvEgImIiIiI4p4MGTK1bdtNEBERaZM5syN/UGyCXeSIiIiIiIiIiEgTBkxERERERERERKQJAyYiIiIiIiIiItKEARMREREREREREWnCgImIiIiIiIiIiDRhwERERERERERERJowYCIiIiIiIiIiIk0YMBERERERERERkSYMmIiIiIiIiIiISBMGTEREREREREREpElCYaGjWx4d2/pIEBEREX0hHyMEEREREcUqFgRMCRLGS5Q4niAiIiL6ohIk0P0vHi9LiIiIiGILCwKmMrXTYRFERERERERERER6OAYTERERERERERFpwoCJiIiIiIiIiIg0YcBERERERERERESaMGAiIiIiIiIiIiJNGDAREREREREREZEmDJiIiIiIiIiIiEgTBkxERERERERERKQJAyYiIiIiIiIiItKEARMREREREREREWnCgImIiIiIiIiIiDRhwERERERERERERJowYCIiIiIiIiIiIk0YMBERERERERERkSYMmIiIiIiIiIiISBMGTEREREREREREpAkDJiIiIiIiIiIi0oQBExERERERERERacKAiYiIiIiIiIiINGHAREREREREREREmjBgIiIiIiIiIiIiTRIKIiIiIvrqnNzx5Mw/TwURERGREO/ffRJ2xoCJiIiI6Cv09k2EeCOIiIiIYka8T5/sHmIRERERUYyJeP8pIoIXeERERGQoQYJ4CRLFE/bBgImIiIiIiIiIiDThIN9ERERERERERKQJAyYiIiIiIiIiItKEARMREREREREREWnCgImIiIiIiIiIiDRhwERERERERERERJowYCIiIiIiIiIiIk0YMBERERERERERkSYMmIiIiIiIiIiISBMGTEREREREREREpAkDJiIiIiIiIiIi0oQBExERERERERERacKAiYiIiIiIiIiINGHAREREREREREREmjBgIiIiIiIiIiIiTRgwERERERERERGRJgyYiIiIiIiIiIhIEwZMRERERERERESkCQMmIiIiIiIiIiLShAETERERERERERFpwoCJiIiIiIiIiIg0YcBERERERERERESaMGAiIiIiIiIiIiJNGDAREREREREREZEmDJiIiIiIiIiIiEgTBkxERERERERERKQJAyYiIiIiIiIiItKEARMREREREREREWnyfwAAAP//U0kxgAAAAAZJREFUAwAnpwZCmTgwNgAAAABJRU5ErkJggg==)
#
# ---
#
# ### 5. 에이전트 맞춤 설정 완성 및 저장
# - **Instructions**: 이커머스 도메인 규칙 및 주요 키 컬럼(`session_id`, `user_id`, `created_at` 등) 정의 추가
# - **Verified queries**: 검증된 신뢰할 수 있는 골든 쿼리 쌍 2건 등록
# - **Glossary**: Knowledge Catalog에서 가져온 55개 비즈니스 용어가 에이전트에 연동된 상태 확인
# - 상단의 **`Save`**를 클릭하여 에이전트를 저장하고, **`Publish`**를 클릭하여 버전을 배포한 후, **`Share`**를 통해 팀원들에게 공유합니다.
#
# ---
#
# ### 6. 추가 테스트 자연어 질의 시나리오
#
# Dataplex `sql-mapping` Aspect 세부 정의와 완전한 Text-to-SQL 레퍼런스 쿼리는 [agent_test_queries_ko.md](../resources/agent_test_queries_ko.md)를 참고하세요.
#
# 1. **채널별 장바구니 포기 트렌드**:
#    - `"유입 마케팅 채널별로 장바구니 이탈율을 계산해서 이탈율이 높은 순으로 정렬해줘."`
# 2. **마진율 및 환불률 분석**:
#    - `"여성 의류 중에서 상품 마진이 40% 이상인 제품들의 환불률을 브랜드별로 계산해줘."`
# 3. **휴면 고객 유입 분포**:
#    - `"휴면 고객들이 가장 많이 유입되었던 가입 경로 3가지는 무엇인가요?"`
