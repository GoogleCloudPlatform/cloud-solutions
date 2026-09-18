# Agentic Data Cloud & Knowledge Catalog 데모 실습 가이드

## 개요

**Agentic Data Cloud Demo** 실습은 Google Cloud 상에서 AI 대응형 데이터 클라우드
인프라를 구축하고, Google Cloud Dataplex, BigQuery, Gemini 모델을 연동하여
고도화된 데이터 분석 및 거버넌스 파이프라인을 실습하는 과정을 안내합니다.

본 실습에서는 BigQuery에 준비된 전자상거래 데이터를 활용하여 Google Colab
Enterprise 환경에서 자동화된 메타데이터 파이프라인을 실행합니다:

- **데이터 프로파일링 및 품질 스캔 자동화**: Dataplex DataScan API를 통해 테이블
  프로파일 분석 및 동적 품질 검증 규칙을 실행합니다.
- **자동화된 컬럼 인사이트**: 데이터셋 테이블에 대한 지능형 컬럼 설명 및
  문서화를 생성합니다.
- **관계형 비즈니스 용어집(Glossary) 구축**: 구조화된 비즈니스 분류 체계를
  로드하고 용어(Terms)를 BigQuery 실제 스키마에 매핑합니다.
- **BigQuery 속성 그래프(Property Graph) 분석**: 전자상거래 고객, 주문, 상품
  관계를 그래프로 구성하고 GQL 문법을 사용한 다중 홉(Multi-hop) 분석을
  수행합니다.
- **BigQuery 생성형 AI & 벡터 검색**: BigQuery 원격 연결을 통해 Gemini 모델을
  호출하고 임베딩 생성 및 시맨틱 유사도 검색을 실행합니다.
- **BigQuery SQL AI 함수**: SQL 레벨의 고수준 선언적 AI 함수(`AI.CLASSIFY`,
  `AI.SIMILARITY`, `AI.IF`, `AI.SEARCH`, 증류)를 적용합니다.

---

## 사전 준비 사항

실습 진행을 위해 다음 항목을 확인합니다:

- 최신 웹 브라우저(Google Chrome 권장)를 사용합니다.
- Qwiklabs 패널에 표시된 실습 **소요 시간**을 확인합니다. 실습을 시작하면 중간에
  일시 중지할 수 없으므로 제한 시간 내에 완료할 수 있도록 일정을 확인합니다.
- 개인 Google Cloud 계정을 사용하지 마십시오. 본 실습을 위해 별도의 전용
  프로젝트와 임시 학생 계정이 제공됩니다.
- 계정 충돌을 방지하기 위해 Google Chrome의 **시크릿 창(Incognito Window)**에서
  실습을 진행합니다.

---

## 실습 시작

Qwiklabs 화면에서 **Start Lab** 버튼을 클릭합니다. 실습 환경이 시작되면
백그라운드에서 다음 리소스가 자동 구성됩니다:

- BigQuery, Dataplex, Vertex AI 등 필수 API가 활성화된 격리된 Google Cloud
  프로젝트.
- 7개 전자상거래 테이블(`distribution_centers`, `events`, `inventory_items`,
  `order_items`, `orders`, `products`, `users`)이 적재된 `thelook_ecommerce`
  BigQuery 데이터셋.
- 전용 가상 사설망(VPC) 네트워크(`adc-demo-vpc`) 및 프라이빗 서브넷.
- VPC에 연결된 사전 구성 **Colab Enterprise 런타임 템플릿**.
- 실습용 주피터 노트북 7종과 비즈니스 용어집 JSON 파일이 업로드된 Google Cloud
  Storage 버킷.

---

## Google Cloud 콘솔 로그인

### 학생 자격 증명 확인

Qwiklabs 화면의 **Connection Details** 패널에서 임시 **Username**과
**Password**를 확인하고 복사합니다.

### 시크릿 모드로 콘솔 접속

1.  브라우저에서 새 **시크릿 창**을 엽니다.
1.  [Google Cloud 콘솔](https://console.cloud.google.com)로 이동합니다.
1.  복사한 학생 **Username**을 입력하고 **다음**을 클릭합니다.
1.  임시 **Password**를 입력하고 **다음**을 클릭합니다.
1.  이용약관에 동의합니다. 복구 옵션 설정이나 무료 체험판 등록을 진행하지
    마십시오.

---

## 1단계: 실습 출력값(Student Visible Outputs) 확인

Qwiklabs 인터페이스의 **Student Visible Outputs** 섹션에서 다음 값을 확인합니다:

- **Colab Runtime Template ID**: 사전 배포된 Colab Enterprise 런타임 템플릿
  이름.
- **Notebooks GCS Bucket**: 실습 노트북이 저장된 Cloud Storage 버킷.
- **Google Cloud Project ID**: 실습용 Google Cloud 프로젝트 ID.
- **Google Cloud Region**: 리소스가 배포된 기본 리전 (예: `us-central1`).
- **BigQuery Dataset ID**: 데이터셋 식별자 (`thelook_ecommerce`).

> [!NOTE]
>
> 모든 노트북은 영어(기본 파일명) 및 한국어(`_ko` 접미사) 버전으로 함께
> 제공됩니다. 선호하는 언어 버전을 선택하여 가져옵니다.

---

## 2단계: Colab Enterprise 접속

1.  Google Cloud 콘솔 상단 검색창에 **Colab Enterprise**를 입력하고 검색
    결과에서 선택합니다.
1.  상단 툴바 우측의 **리전(Region)** 드롭다운이 실습 배포 리전(**Google Cloud
    Region**, 예: `us-central1`)과 일치하는지 확인합니다.
1.  좌측 탐색 메뉴에서 **My Notebooks**를 클릭합니다.

---

## 3단계: Cloud Storage로부터 노트북 가져오기

Cloud Storage에 저장된 실습 노트북을 콘솔 GUI 탐색기를 통해 Colab Enterprise로
가져옵니다:

1.  Colab Enterprise 화면 상단의 **Import notebook** 버튼을 클릭합니다.
1.  가져오기 소스로 **Google Cloud Storage**를 선택합니다.
1.  **Browse** 버튼을 클릭하여 Cloud Storage 버킷 선택 창을 엽니다.
1.  목록에서 **Notebooks GCS Bucket**을 선택합니다.
1.  버킷 내에서 실행하고자 하는 주피터 노트북 파일(영어:
    `01_data_profile_quality.ipynb` / 한국어:
    `01_data_profile_quality_ko.ipynb`)을 선택합니다.
1.  **Select**를 클릭한 후 **Import** 버튼을 클릭합니다.
1.  실습 순서에 따라 필요한 노트북을 순차적으로 가져옵니다.

---

## 4단계: 사전 구성 런타임 템플릿 연결

1.  가져온 노트북을 Colab Enterprise 에디터에서 엽니다.
1.  에디터 우측 상단의 **연결(Connect)** 버튼 옆 드롭다운 화살표를 클릭하고
    **Connect to a runtime template**을 선택합니다.
1.  **Colab Runtime Template ID**로 지정된 사전 구성 템플릿(예:
    `adc-demo-template-...`)을 선택합니다.
1.  런타임 VM 할당 및 연결이 완료될 때까지 대기합니다.

---

## 5단계: 분석 파이프라인 노트북 실행

노트북을 순차적으로 실행하며 실습을 진행합니다:

### 노트북 01: 데이터 프로파일 및 데이터 품질 관리

- `01_data_profile_quality_ko.ipynb`를 실행합니다.
- Dataplex DataScan API 호출 함수를 설정하고 `users`, `orders` 테이블에 대한
  자동화 프로파일링을 구동합니다.
- BigQuery를 통해 데이터 품질 검증 결과와 메타데이터 테이블을 조회합니다.

### 노트북 02 & 03: 데이터 인사이트 및 컬럼 메타데이터 생성

- `02_data_insight_ko.ipynb` 및 `03_dataset_insights_ko.ipynb`를 실행합니다.
- Dataplex DataScan을 통해 지능형 컬럼 설명을 생성하고 Knowledge Catalog
  메타데이터 라벨로 게시합니다.

### 노트북 04: 관계형 비즈니스 용어집(Glossary) 구축

- `04_glossary_setup_ko.ipynb`를 실행합니다.
- `resources/business_glossary_ko.json`에 정의된 비즈니스 카테고리, 용어, 동의어
  체계를 Dataplex Glossary로 등록합니다.
- 용어(Terms)를 실제 BigQuery 테이블 및 컬럼과 링크합니다.

### 노트북 05: BigQuery Graph 분석 (GQL)

- `05_graph_analysis_ko.ipynb`를 실행합니다.
- 고객, 상품, 물류센터 데이터를 결합하여 Property Graph를 선언합니다.
- GQL 패턴 매칭(`MATCH (c:Customer)-[:ordered]->(p:Product)`) 쿼리를 실행하여
  추천 네트워크를 분석합니다.

### 노트북 06 & 07: BigQuery AI 및 Gemini 모델 연동

- `06_bigquery_ai_ml_demo_ko.ipynb` 및 `07_bigquery_ai_functions_ko.ipynb`를
  실행합니다.
- 사전 구성된 `vertex-connection` 원격 연결을 확인합니다.
- SQL 쿼리 내에서 직접 Gemini LLM을 호출하여 텍스트 분류, 벡터 임베딩 생성 및
  코사인 유사도 검색을 수행합니다.
- `AI.CLASSIFY`, `AI.SIMILARITY`, `AI.SEARCH` 등 고수준 SQL AI 함수를
  테스트합니다.

---

## 6단계: 실습 종료

실습이 완료되면:

1.  Qwiklabs 브라우저 탭으로 돌아갑니다.
1.  **End Lab** 버튼을 클릭하고 종료를 확인합니다.
1.  실습 환경에 생성된 모든 임시 리소스가 자동으로 삭제됩니다.
