# 데이터 분석 플레이그라운드

이 디렉터리는 BigQuery 퍼블릭 데이터셋인 `thelook_ecommerce`를 탐색, 분석 및
테스트하기 위한 공간입니다.

## 구성 내용

- `notebooks/`: 대화형 분석 및 메타데이터 설정을 위한 Jupyter 노트북 파일들
  (기본 영어 및 한국어 `_ko` 버전 제공)
    - `01_data_profile_quality.ipynb` / `01_data_profile_quality_ko.ipynb`:
      데이터 프로파일 및 데이터 품질 스캔 규칙을 자동으로 생성하고 일괄
      실행하는 파이프라인 노트북.
    - `02_data_insight.ipynb` / `02_data_insight_ko.ipynb`:
      Dataplex DataScans를 활용하여 컬럼 설명을 자동으로 생성하고 BigQuery
      스키마와 동기화하는 노트북.
    - `03_dataset_insights.ipynb` / `03_dataset_insights_ko.ipynb`:
      데이터셋 탐색적 분석 및 통계 분석 노트북.
    - `04_glossary_setup.ipynb` / `04_glossary_setup_ko.ipynb`:
      비즈니스 용어집 데이터를 Dataplex에 적재하는 노트북.
    - `05_graph_analysis.ipynb` / `05_graph_analysis_ko.ipynb`:
      BigQuery 속성 그래프(Property Graph) 구축, GQL(Graph Query Language) 분석
      및 네이티브 시각화 실습.
    - `06_bigquery_ai_ml_demo.ipynb` / `06_bigquery_ai_ml_demo_ko.ipynb`:
      BigQuery 생성형 AI 및 머신러닝 분석 실습 (원격 모델, 개인화 추천 메일,
      카탈로그 번역 및 태그 추출, 상품 임베딩 및 벡터 검색).
    - `07_bigquery_ai_functions.ipynb` / `07_bigquery_ai_functions_ko.ipynb`:
      BigQuery 고수준 AI 함수 실습 (AI.CLASSIFY, AI.SIMILARITY, AI.IF,
      AI.SEARCH, Distillation).

- `resources/`: 용어집 정의 및 매핑 설정을 위한 리소스 파일들
    - [agent_test_queries_ko.md](resources/agent_test_queries_ko.md) /
      [영문](resources/agent_test_queries.md): 대화형 분석 에이전트 검증을
      위한 물리 매핑 규칙 가이드 및 시나리오별 예상 SQL 레퍼런스 문서.
    - `business_glossary_ko.json` / `business_glossary.json`: 비즈니스 용어
      정의 메타데이터.

## 로컬 개발 및 테스트 가이드

이 프로젝트의 노트북들은 기본적으로 Colab Enterprise 템플릿 등 클라우드 런타임
환경에서 실행하도록 설계되었습니다. 다만, 로컬 개발 환경에서 노트북을 직접
테스트하려는 경우 아래 설정을 참고하십시오.

### 의존성 설치 및 가상환경 구성

프로젝트 루트 폴더 혹은 `analytics/` 디렉터리에 있는 `pyproject.toml`을 활용하여
의존성을 설치할 수 있습니다. 빠르고 신뢰성 있는 패키지 동기화를 위해
**[uv](https://github.com/astral-sh/uv)** 사용을 권장합니다.

```bash
# 로컬 가상환경(.venv) 생성 및 의존성 동기화
uv sync --frozen
```

- `.venv/`: 분석 작업 및 로컬 테스트에 필요한 라이브러리들이 설치되는 독립형
  가상환경 디렉터리입니다.
